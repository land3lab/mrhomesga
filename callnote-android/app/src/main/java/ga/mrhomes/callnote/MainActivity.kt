package ga.mrhomes.callnote

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.util.Base64
import android.webkit.ValueCallback
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebView
import android.webkit.WebViewClient
import android.widget.Toast
import androidx.activity.OnBackPressedCallback
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.content.ContextCompat
import org.json.JSONObject

class MainActivity : AppCompatActivity() {

    companion object {
        const val ACTION_PROCESS_RECORDING = "ga.mrhomes.callnote.PROCESS_RECORDING"
        const val EXTRA_AUDIO_URI = "audio_uri"
        const val EXTRA_AUDIO_NAME = "audio_name"
        const val EXTRA_CALL_PHONE = "call_phone"
        const val EXTRA_CALL_TYPE = "call_type"
        const val EXTRA_CALL_NAME = "call_name"
        const val APP_URL = "https://land3lab.github.io/mrhomesga/callnote/"
        private const val MAX_FILE_BYTES = 19L * 1024 * 1024
        private const val JS_CHUNK_CHARS = 256 * 1024
    }

    private lateinit var webView: WebView
    private var pageLoaded = false
    private var pendingAudio: Pair<Uri, String>? = null // (uri, 파일명) — 페이지 로드 후 주입
    private var pendingCall: CallInfo? = null // 방금 통화의 상대 번호/이름 — 녹음과 함께 주입
    private var fileChooserCallback: ValueCallback<Array<Uri>>? = null

    private val fileChooserLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            val uri = result.data?.data
            fileChooserCallback?.onReceiveValue(if (uri != null) arrayOf(uri) else arrayOf())
            fileChooserCallback = null
        }

    private val permissionLauncher =
        registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) { }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)

        webView = WebView(this)
        setContentView(webView)

        with(webView.settings) {
            javaScriptEnabled = true
            domStorageEnabled = true // 상담 기록·API 키 저장(localStorage)에 필요
            mediaPlaybackRequiresUserGesture = true
            allowFileAccess = false
        }

        webView.webViewClient = object : WebViewClient() {
            override fun onPageFinished(view: WebView?, url: String?) {
                pageLoaded = true
                // 웹 화면에 "자동 감지 켜짐" 표시를 위해 네이티브 실행 상태를 알린다
                webView.evaluateJavascript(
                    "window.__nativeMonitoring && window.__nativeMonitoring(true)", null
                )
                flushPendingAudio()
            }

            override fun shouldOverrideUrlLoading(
                view: WebView?,
                request: WebResourceRequest?,
            ): Boolean {
                val url = request?.url ?: return false
                // 앱 화면(github.io) 밖으로 나가는 링크(API 키 발급 등)는 브라우저로
                return if (url.host != Uri.parse(APP_URL).host) {
                    try {
                        startActivity(Intent(Intent.ACTION_VIEW, url))
                    } catch (_: Exception) {
                    }
                    true
                } else false
            }
        }

        webView.webChromeClient = object : WebChromeClient() {
            override fun onShowFileChooser(
                view: WebView?,
                callback: ValueCallback<Array<Uri>>?,
                params: FileChooserParams?,
            ): Boolean {
                fileChooserCallback?.onReceiveValue(arrayOf())
                fileChooserCallback = callback
                val pick = Intent(Intent.ACTION_GET_CONTENT).apply {
                    addCategory(Intent.CATEGORY_OPENABLE)
                    type = "audio/*"
                }
                fileChooserLauncher.launch(Intent.createChooser(pick, "녹음 파일 선택"))
                return true
            }
        }

        onBackPressedDispatcher.addCallback(this, object : OnBackPressedCallback(true) {
            override fun handleOnBackPressed() {
                if (webView.canGoBack()) webView.goBack() else finish()
            }
        })

        requestNeededPermissions()
        MonitorService.start(this) // "매통이 실행 중" 지속 알림 + 프로세스 유지 시작
        webView.loadUrl(APP_URL)
        handleIntent(intent)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        handleIntent(intent)
    }

    private fun requestNeededPermissions() {
        val wanted = mutableListOf(
            Manifest.permission.READ_PHONE_STATE,
            Manifest.permission.READ_CALL_LOG,
        )
        if (Build.VERSION.SDK_INT >= 33) {
            wanted += Manifest.permission.READ_MEDIA_AUDIO
            wanted += Manifest.permission.POST_NOTIFICATIONS
        } else {
            wanted += Manifest.permission.READ_EXTERNAL_STORAGE
        }
        val missing = wanted.filter {
            ContextCompat.checkSelfPermission(this, it) != PackageManager.PERMISSION_GRANTED
        }
        if (missing.isNotEmpty()) permissionLauncher.launch(missing.toTypedArray())
    }

    private fun handleIntent(intent: Intent?) {
        intent ?: return
        when {
            // 통화 종료 알림에서 진입
            intent.action == ACTION_PROCESS_RECORDING -> {
                val uriStr = intent.getStringExtra(EXTRA_AUDIO_URI) ?: return
                val name = intent.getStringExtra(EXTRA_AUDIO_NAME) ?: "통화녹음.m4a"
                pendingAudio = Uri.parse(uriStr) to name
                val phone = intent.getStringExtra(EXTRA_CALL_PHONE) ?: ""
                pendingCall = if (phone.isNotBlank()) {
                    CallInfo(
                        phone,
                        intent.getStringExtra(EXTRA_CALL_TYPE) ?: "",
                        intent.getStringExtra(EXTRA_CALL_NAME) ?: "",
                    )
                } else null
                flushPendingAudio()
            }
            // 공유 시트에서 진입
            intent.action == Intent.ACTION_SEND -> {
                @Suppress("DEPRECATION")
                val uri: Uri? = if (Build.VERSION.SDK_INT >= 33) {
                    intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
                } else {
                    intent.getParcelableExtra(Intent.EXTRA_STREAM)
                }
                if (uri != null) {
                    pendingAudio = uri to (queryDisplayName(uri) ?: "통화녹음.m4a")
                    flushPendingAudio()
                }
            }
        }
    }

    private fun queryDisplayName(uri: Uri): String? = try {
        contentResolver.query(uri, null, null, null, null)?.use { c ->
            val idx = c.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
            if (idx >= 0 && c.moveToFirst()) c.getString(idx) else null
        }
    } catch (_: Exception) {
        null
    }

    /** 페이지가 준비되면 대기 중인 녹음을 base64 조각으로 웹앱에 주입한다. */
    private fun flushPendingAudio() {
        if (!pageLoaded) return
        val (uri, name) = pendingAudio ?: return
        pendingAudio = null

        val bytes = try {
            contentResolver.openInputStream(uri)?.use { it.readBytes() }
        } catch (_: Exception) {
            null
        }
        if (bytes == null) {
            Toast.makeText(this, "녹음 파일을 읽지 못했습니다", Toast.LENGTH_LONG).show()
            return
        }
        if (bytes.size > MAX_FILE_BYTES) {
            Toast.makeText(this, "파일이 20MB를 넘어 처리할 수 없습니다", Toast.LENGTH_LONG).show()
            return
        }

        val mime = contentResolver.getType(uri) ?: "audio/mp4"
        val b64 = Base64.encodeToString(bytes, Base64.NO_WRAP)
        val jsName = JSONObject.quote(name)
        val jsMime = JSONObject.quote(mime)

        // 통화 상대 정보를 먼저 전달 (연락처 칸 자동 입력 + AI 프롬프트 참고용)
        pendingCall?.let { call ->
            val p = JSONObject.quote(call.number)
            val t = JSONObject.quote(call.type)
            val n = JSONObject.quote(call.contactName)
            webView.evaluateJavascript(
                "window.__nativeCallInfo && window.__nativeCallInfo($p, $t, $n)", null
            )
        }
        pendingCall = null

        // evaluateJavascript는 호출 순서대로 실행되므로 begin → chunk… → end 순서가 보장된다
        webView.evaluateJavascript(
            "window.__nativeShareBegin && window.__nativeShareBegin($jsName, $jsMime)", null
        )
        var offset = 0
        while (offset < b64.length) {
            val end = minOf(offset + JS_CHUNK_CHARS, b64.length)
            webView.evaluateJavascript(
                "window.__nativeShareChunk && window.__nativeShareChunk('${b64.substring(offset, end)}')",
                null,
            )
            offset = end
        }
        webView.evaluateJavascript("window.__nativeShareEnd && window.__nativeShareEnd()", null)
    }
}
