package ga.mrhomes.callnote

import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.os.Build
import android.os.IBinder
import androidx.core.app.NotificationCompat

/**
 * 항상 떠 있는 지속 알림("매통이 실행 중")으로 앱이 통화 감지 대기 중임을 알린다.
 * 프로세스를 살려 두어 통화 종료 감지(CallReceiver)의 신뢰도도 높인다.
 * 앱 실행 시(MainActivity)와 기기 부팅 시(BootReceiver) 모두에서 시작된다.
 */
class MonitorService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(NOTIF_ID, buildNotification())
        return START_STICKY // 시스템이 종료해도 다시 살아난다
    }

    private fun buildNotification(): Notification {
        val nm = getSystemService(Context.NOTIFICATION_SERVICE) as NotificationManager
        nm.createNotificationChannel(
            NotificationChannel(CHANNEL, "매통이 자동 감지", NotificationManager.IMPORTANCE_LOW).apply {
                description = "통화 종료를 감지해 자동으로 매물 정리를 도와줍니다"
                setShowBadge(false)
            }
        )
        val open = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT,
        )
        return NotificationCompat.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_stat_call)
            .setContentTitle("매통이 실행 중")
            .setContentText("통화가 끝나면 자동으로 정리를 도와드려요")
            .setContentIntent(open)
            .setOngoing(true)
            .setShowWhen(false)
            .setPriority(NotificationCompat.PRIORITY_LOW)
            .build()
    }

    companion object {
        private const val CHANNEL = "callnote_monitor"
        private const val NOTIF_ID = 1010

        fun start(ctx: Context) {
            val i = Intent(ctx, MonitorService::class.java)
            try {
                if (Build.VERSION.SDK_INT >= 26) ctx.startForegroundService(i) else ctx.startService(i)
            } catch (_: Exception) {
                // 배경에서 시작 제한에 걸리면 조용히 무시 (앱을 한 번 열면 다시 시작됨)
            }
        }
    }
}
