package ga.mrhomes.callnote

import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Context
import android.content.Intent
import android.net.Uri
import androidx.core.app.NotificationCompat

object NotifyHelper {
    private const val CHANNEL_ID = "callnote_recording"
    private const val NOTIFICATION_ID = 1004

    fun showRecordingNotification(context: Context, audioUri: Uri, fileName: String, call: CallInfo?) {
        val nm = context.getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(
                CHANNEL_ID,
                "통화 녹음 정리",
                NotificationManager.IMPORTANCE_HIGH,
            ).apply { description = "통화가 끝나면 녹음 정리 여부를 물어봅니다" }
        )

        val openIntent = Intent(context, MainActivity::class.java).apply {
            action = MainActivity.ACTION_PROCESS_RECORDING
            putExtra(MainActivity.EXTRA_AUDIO_URI, audioUri.toString())
            putExtra(MainActivity.EXTRA_AUDIO_NAME, fileName)
            if (call != null) {
                putExtra(MainActivity.EXTRA_CALL_PHONE, call.number)
                putExtra(MainActivity.EXTRA_CALL_TYPE, call.type)
                putExtra(MainActivity.EXTRA_CALL_NAME, call.contactName)
            }
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        val pending = PendingIntent.getActivity(
            context,
            (System.currentTimeMillis() % Int.MAX_VALUE).toInt(),
            openIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        val who = call?.let {
            listOf(it.contactName, it.number).filter { s -> s.isNotBlank() }.joinToString(" ")
        }?.takeIf { it.isNotBlank() }
        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_call)
            .setContentTitle(if (who != null) "$who 통화 녹음이 저장됐어요" else "통화 녹음이 저장됐어요")
            .setContentText("자동으로 상담카드를 만드는 중이에요")
            .setStyle(
                NotificationCompat.BigTextStyle()
                    .bigText("$fileName\n자동으로 통화노트가 열려 AI 정리·저장됩니다. (안 열리면 탭하세요)")
            )
            .setContentIntent(pending)
            .setFullScreenIntent(pending, true) // 통화 끝나면 앱이 스스로 열려 자동 정리 (탭 불필요)
            .setCategory(NotificationCompat.CATEGORY_CALL)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()

        try {
            nm.notify(NOTIFICATION_ID, notification)
        } catch (_: SecurityException) {
            // 알림 권한 미허용 — 앱을 열어 권한을 허용해야 한다
        }
        // 전체화면 인텐트가 막히는 기종을 대비해 액티비티 직접 실행도 시도 (실행 중 포그라운드 서비스가 있어 성공률↑)
        try {
            context.startActivity(openIntent)
        } catch (_: Exception) {
            // 백그라운드 실행 제한 등 — 알림(전체화면/탭)으로 대체
        }
    }
}
