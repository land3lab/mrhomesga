package ga.mrhomes.callnote

import android.content.ContentUris
import android.content.Context
import android.net.Uri
import android.os.Build
import android.provider.MediaStore
import androidx.work.Worker
import androidx.work.WorkerParameters

/**
 * 통화 종료 직후 실행되어, 미디어저장소에서 방금 저장된 통화 녹음 파일을 찾아
 * "정리할까요?" 알림을 띄운다. 파일이 아직 저장 안 됐으면 두 번까지 재시도.
 */
class RecordingCheckWorker(context: Context, params: WorkerParameters) :
    Worker(context, params) {

    override fun doWork(): Result {
        val found = findLatestCallRecording(applicationContext, windowSeconds = 10 * 60)
        return if (found != null) {
            val call = findLastCall(applicationContext)
            NotifyHelper.showRecordingNotification(applicationContext, found.first, found.second, call)
            Result.success()
        } else if (runAttemptCount < 2) {
            Result.retry() // WorkManager 기본 백오프(10초~)로 재시도
        } else {
            Result.success() // 녹음이 꺼져 있었거나 못 찾음 — 조용히 종료
        }
    }

    /** 통화기록에서 방금 통화(최근 10분 내)의 상대 번호·수발신 구분·저장된 이름을 가져온다. */
    private fun findLastCall(context: Context): CallInfo? {
        try {
            context.contentResolver.query(
                android.provider.CallLog.Calls.CONTENT_URI,
                arrayOf(
                    android.provider.CallLog.Calls.NUMBER,
                    android.provider.CallLog.Calls.TYPE,
                    android.provider.CallLog.Calls.CACHED_NAME,
                    android.provider.CallLog.Calls.DATE,
                ),
                "${android.provider.CallLog.Calls.DATE} >= ?",
                arrayOf((System.currentTimeMillis() - 10 * 60 * 1000).toString()),
                "${android.provider.CallLog.Calls.DATE} DESC",
            )?.use { c ->
                if (c.moveToFirst()) {
                    val type = when (c.getInt(1)) {
                        android.provider.CallLog.Calls.INCOMING_TYPE -> "수신"
                        android.provider.CallLog.Calls.OUTGOING_TYPE -> "발신"
                        else -> ""
                    }
                    return CallInfo(c.getString(0) ?: "", type, c.getString(2) ?: "")
                }
            }
        } catch (_: SecurityException) {
            // 통화기록 권한 미허용 — 번호 자동 입력 없이 진행
        }
        return null
    }

    private fun findLatestCallRecording(context: Context, windowSeconds: Long): Pair<Uri, String>? {
        val sinceEpochSec = System.currentTimeMillis() / 1000 - windowSeconds
        val projection = if (Build.VERSION.SDK_INT >= 29) {
            arrayOf(
                MediaStore.Audio.Media._ID,
                MediaStore.Audio.Media.DISPLAY_NAME,
                MediaStore.Audio.Media.DATE_ADDED,
                MediaStore.Audio.Media.RELATIVE_PATH,
            )
        } else {
            @Suppress("DEPRECATION")
            arrayOf(
                MediaStore.Audio.Media._ID,
                MediaStore.Audio.Media.DISPLAY_NAME,
                MediaStore.Audio.Media.DATE_ADDED,
                MediaStore.Audio.Media.DATA,
            )
        }
        try {
            context.contentResolver.query(
                MediaStore.Audio.Media.EXTERNAL_CONTENT_URI,
                projection,
                "${MediaStore.Audio.Media.DATE_ADDED} >= ?",
                arrayOf(sinceEpochSec.toString()),
                "${MediaStore.Audio.Media.DATE_ADDED} DESC",
            )?.use { cursor ->
                val idCol = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media._ID)
                val nameCol = cursor.getColumnIndexOrThrow(MediaStore.Audio.Media.DISPLAY_NAME)
                val pathCol = cursor.getColumnIndex(projection[3])
                while (cursor.moveToNext()) {
                    val name = cursor.getString(nameCol) ?: continue
                    val path = if (pathCol >= 0) cursor.getString(pathCol) ?: "" else ""
                    val hay = "$path/$name".lowercase()
                    // 삼성: Recordings/Call/통화 녹음 이름_날짜.m4a — 경로나 파일명에
                    // call/통화가 들어간 최신 오디오만 통화 녹음으로 간주
                    if (hay.contains("call") || hay.contains("통화")) {
                        val uri = ContentUris.withAppendedId(
                            MediaStore.Audio.Media.EXTERNAL_CONTENT_URI,
                            cursor.getLong(idCol),
                        )
                        return uri to name
                    }
                }
            }
        } catch (_: SecurityException) {
            // 저장소 권한이 아직 없음 — 앱을 한 번 열어 권한을 허용해야 한다
        }
        return null
    }
}

data class CallInfo(val number: String, val type: String, val contactName: String)
