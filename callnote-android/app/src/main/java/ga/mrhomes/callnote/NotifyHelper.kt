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

    fun showRecordingNotification(context: Context, audioUri: Uri, fileName: String) {
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
            addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        }
        val pending = PendingIntent.getActivity(
            context,
            (System.currentTimeMillis() % Int.MAX_VALUE).toInt(),
            openIntent,
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )

        val notification = NotificationCompat.Builder(context, CHANNEL_ID)
            .setSmallIcon(R.drawable.ic_stat_call)
            .setContentTitle("통화 녹음이 저장됐어요")
            .setContentText("탭하면 AI 정리 여부를 선택합니다")
            .setStyle(
                NotificationCompat.BigTextStyle()
                    .bigText("$fileName\n탭하면 통화노트가 열리고, AI로 정리할지 선택할 수 있어요.")
            )
            .setContentIntent(pending)
            .setAutoCancel(true)
            .setPriority(NotificationCompat.PRIORITY_HIGH)
            .build()

        try {
            nm.notify(NOTIFICATION_ID, notification)
        } catch (_: SecurityException) {
            // 알림 권한 미허용 — 앱을 열어 권한을 허용해야 한다
        }
    }
}
