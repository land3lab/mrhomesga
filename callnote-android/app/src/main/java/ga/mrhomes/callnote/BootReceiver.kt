package ga.mrhomes.callnote

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent

/**
 * 기기 부팅이 끝나면 감지 서비스를 자동으로 다시 시작한다.
 * (BOOT_COMPLETED는 배경 포그라운드 서비스 시작이 허용되는 예외 상황)
 */
class BootReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        when (intent.action) {
            Intent.ACTION_BOOT_COMPLETED,
            "android.intent.action.QUICKBOOT_POWERON",
            "com.htc.intent.action.QUICKBOOT_POWERON" -> MonitorService.start(context)
        }
    }
}
