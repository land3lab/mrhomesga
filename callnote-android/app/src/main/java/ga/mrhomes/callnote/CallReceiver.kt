package ga.mrhomes.callnote

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.telephony.TelephonyManager
import androidx.work.OneTimeWorkRequestBuilder
import androidx.work.WorkManager
import java.util.concurrent.TimeUnit

/**
 * 전화 상태 변화를 받아 "통화가 실제로 있었고 방금 끝났다"를 감지한다.
 * 통화 종료(IDLE) 시점에 몇 초 뒤 녹음 파일 탐지 작업을 예약한다
 * (삼성 전화 앱이 녹음 파일을 저장할 시간을 준다).
 */
class CallReceiver : BroadcastReceiver() {

    companion object {
        // PHONE_STATE 브로드캐스트는 통화 한 번에 여러 번 오므로(RINGING→OFFHOOK→IDLE)
        // "통화 중이었다" 여부를 프로세스 내 정적 플래그로 추적한다.
        @Volatile
        private var sawOffhook = false
    }

    override fun onReceive(context: Context, intent: Intent) {
        if (intent.action != TelephonyManager.ACTION_PHONE_STATE_CHANGED) return
        when (intent.getStringExtra(TelephonyManager.EXTRA_STATE)) {
            TelephonyManager.EXTRA_STATE_OFFHOOK -> sawOffhook = true
            TelephonyManager.EXTRA_STATE_IDLE -> {
                if (!sawOffhook) return // 부재중 등 실제 통화가 없었던 경우
                sawOffhook = false
                val work = OneTimeWorkRequestBuilder<RecordingCheckWorker>()
                    .setInitialDelay(6, TimeUnit.SECONDS)
                    .build()
                WorkManager.getInstance(context).enqueue(work)
            }
        }
    }
}
