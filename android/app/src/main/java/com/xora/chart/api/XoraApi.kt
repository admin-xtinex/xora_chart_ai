package com.xora.chart.api

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass
import com.squareup.moshi.Moshi
import com.squareup.moshi.Types
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import java.util.concurrent.TimeUnit

@JsonClass(generateAdapter = true)
data class Opportunity(
    val id: String,
    val symbol: String,
    val status: String? = null,
    val rank_score: Double? = null,
    val last_price: Double? = null,
    val best_match: PatternMatch? = null,
    val trade: TradeLevels? = null,
    val decision: TradeDecision? = null,
    val market_analysis: MarketAnalysis? = null,
)

@JsonClass(generateAdapter = true)
data class PatternMatch(
    val pattern_name: String? = null,
    val similarity: Double? = null,
    val direction: String? = null,
)

@JsonClass(generateAdapter = true)
data class TradeLevels(
    val side: String? = null,
    val entry: Double? = null,
    val stop_loss: Double? = null,
    val take_profit_1: Double? = null,
    val risk_reward: Double? = null,
    val confidence: Double? = null,
)

@JsonClass(generateAdapter = true)
data class TradeDecision(
    val action: String? = null,
    val reason: String? = null,
)

@JsonClass(generateAdapter = true)
data class MarketAnalysis(
    val score: Double? = null,
    val bias: String? = null,
    val regime: String? = null,
)

@JsonClass(generateAdapter = true)
data class Position(
    val id: String,
    val symbol: String,
    val side: String? = null,
    val status: String? = null,
    val mode: String? = null,
    val entry: Double? = null,
    val stop_loss: Double? = null,
    val take_profit_1: Double? = null,
    val quantity: Double? = null,
    val leverage: Int? = null,
    val realized_pnl: Double? = null,
)

@JsonClass(generateAdapter = true)
data class TradeSummary(
    val open_count: Int = 0,
    val closed_count: Int = 0,
    val win_rate: Double = 0.0,
    val total_realized_pnl: Double = 0.0,
    val wins: Int = 0,
    val losses: Int = 0,
)

@JsonClass(generateAdapter = true)
data class Settings(
    val auto_trade: Boolean = false,
    val trade_mode: String = "demo",
)

@JsonClass(generateAdapter = true)
data class Health(
    val status: String? = null,
    val auto_trade: Boolean? = null,
    val opportunities_cached: Int? = null,
    val positions_open: Int? = null,
    val binance: String? = null,
)

class XoraApi(baseUrl: String) {
    private var base = baseUrl.trimEnd('/')
    private val client = OkHttpClient.Builder()
        .connectTimeout(20, TimeUnit.SECONDS)
        .readTimeout(60, TimeUnit.SECONDS)
        .build()
    private val moshi = Moshi.Builder().add(KotlinJsonAdapterFactory()).build()
    private val jsonMedia = "application/json".toMediaType()

    fun setBaseUrl(url: String) {
        base = url.trimEnd('/')
    }

    private suspend fun get(path: String): String = withContext(Dispatchers.IO) {
        val req = Request.Builder().url("$base$path").get().build()
        client.newCall(req).execute().use { res ->
            val body = res.body?.string().orEmpty()
            if (!res.isSuccessful) error(body.ifBlank { "HTTP ${res.code}" })
            body
        }
    }

    private suspend fun post(path: String, json: String = "{}"): String = withContext(Dispatchers.IO) {
        val req = Request.Builder()
            .url("$base$path")
            .post(json.toRequestBody(jsonMedia))
            .build()
        client.newCall(req).execute().use { res ->
            val body = res.body?.string().orEmpty()
            if (!res.isSuccessful) error(body.ifBlank { "HTTP ${res.code}" })
            body
        }
    }

    private suspend fun patch(path: String, json: String): String = withContext(Dispatchers.IO) {
        val req = Request.Builder()
            .url("$base$path")
            .patch(json.toRequestBody(jsonMedia))
            .build()
        client.newCall(req).execute().use { res ->
            val body = res.body?.string().orEmpty()
            if (!res.isSuccessful) error(body.ifBlank { "HTTP ${res.code}" })
            body
        }
    }

    suspend fun health(): Health =
        moshi.adapter(Health::class.java).fromJson(get("/api/v1/health"))!!

    suspend fun opportunities(): List<Opportunity> {
        val type = Types.newParameterizedType(List::class.java, Opportunity::class.java)
        return moshi.adapter<List<Opportunity>>(type).fromJson(get("/api/v1/opportunities?limit=40")) ?: emptyList()
    }

    suspend fun runCycle() {
        post("/api/v1/cycles/run")
    }

    suspend fun settings(): Settings =
        moshi.adapter(Settings::class.java).fromJson(get("/api/v1/settings")) ?: Settings()

    suspend fun setAutoTrade(enabled: Boolean): Settings {
        val body = """{"auto_trade":$enabled}"""
        return moshi.adapter(Settings::class.java).fromJson(patch("/api/v1/settings", body)) ?: Settings()
    }

    suspend fun positions(): List<Position> {
        val type = Types.newParameterizedType(List::class.java, Position::class.java)
        return moshi.adapter<List<Position>>(type).fromJson(get("/api/v1/positions")) ?: emptyList()
    }

    suspend fun summary(): TradeSummary =
        moshi.adapter(TradeSummary::class.java).fromJson(get("/api/v1/positions/history/summary"))
            ?: TradeSummary()

    suspend fun openTrade(opportunityId: String) {
        post("/api/v1/positions", """{"opportunity_id":"$opportunityId"}""")
    }

    suspend fun closeTrade(positionId: String) {
        post("/api/v1/positions/$positionId/close", "{}")
    }
}
