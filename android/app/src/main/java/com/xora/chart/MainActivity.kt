package com.xora.chart

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.xora.chart.api.Opportunity
import com.xora.chart.api.Position
import com.xora.chart.api.TradeSummary
import com.xora.chart.api.XoraApi
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch

private val Bg = Color(0xFF0A0E17)
private val Card = Color(0xFF121826)
private val Border = Color(0xFF1C2538)
private val TextMain = Color(0xFFE2E8F0)
private val TextDim = Color(0xFF94A3B8)
private val Blue = Color(0xFF3B82F6)
private val Green = Color(0xFF34D399)
private val Rose = Color(0xFFF87171)
private val Amber = Color(0xFFFBBF24)
private val Violet = Color(0xFFA78BFA)

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme(colorScheme = darkColorScheme(background = Bg, surface = Card)) {
                Surface(Modifier = Modifier.fillMaxSize(), color = Bg) {
                    XoraApp()
                }
            }
        }
    }
}

@Composable
fun XoraApp() {
    var apiBase by remember { mutableStateOf(BuildConfig.DEFAULT_API_BASE) }
    val api = remember(apiBase) { XoraApi(apiBase) }
    var tab by remember { mutableStateOf(0) }
    var autoTrade by remember { mutableStateOf(false) }
    var status by remember { mutableStateOf("…") }
    val scope = rememberCoroutineScope()

    LaunchedEffect(api) {
        while (true) {
            try {
                val h = api.health()
                val s = api.settings()
                autoTrade = s.auto_trade
                status = "API ok · opp ${h.opportunities_cached ?: 0} · open ${h.positions_open ?: 0}"
            } catch (e: Exception) {
                status = "Offline: ${e.message?.take(40)}"
            }
            delay(12_000)
        }
    }

    Column(Modifier = Modifier.fillMaxSize()) {
        // Header
        Column(
            Modifier
                .fillMaxWidth()
                .background(Card)
                .padding(16.dp)
        ) {
            Text("XORA Chart AI", color = TextMain, fontWeight = FontWeight.Bold, fontSize = 18.sp)
            Text(status, color = TextDim, fontSize = 11.sp)
            Spacer(Modifier = Modifier.height(8.dp))
            OutlinedTextField(
                value = apiBase,
                onValueChange = { apiBase = it },
                label = { Text("API base URL") },
                singleLine = true,
                modifier = Modifier.fillMaxWidth(),
                colors = OutlinedTextFieldDefaults.colors(
                    focusedTextColor = TextMain,
                    unfocusedTextColor = TextMain,
                    focusedBorderColor = Blue,
                    unfocusedBorderColor = Border,
                    focusedLabelColor = TextDim,
                    unfocusedLabelColor = TextDim,
                )
            )
        }

        TabRow(selectedTabIndex = tab, containerColor = Card, contentColor = Blue) {
            Tab(selected = tab == 0, onClick = { tab = 0 }, text = { Text("Opportunities") })
            Tab(selected = tab == 1, onClick = { tab = 1 }, text = { Text("Trades") })
        }

        when (tab) {
            0 -> OpportunitiesScreen(api, autoTrade) { enabled ->
                scope.launch {
                    try {
                        autoTrade = api.setAutoTrade(enabled).auto_trade
                    } catch (_: Exception) {
                    }
                }
            }
            1 -> TradesScreen(api)
        }
    }
}

@Composable
fun OpportunitiesScreen(api: XoraApi, autoTrade: Boolean, onToggleAuto: (Boolean) -> Unit) {
    var items by remember { mutableStateOf<List<Opportunity>>(emptyList()) }
    var selected by remember { mutableStateOf<Opportunity?>(null) }
    var scanning by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun refresh() {
        scope.launch {
            try {
                items = api.opportunities()
                if (selected == null) selected = items.firstOrNull()
                else selected = items.find { it.id == selected?.id } ?: items.firstOrNull()
                error = null
            } catch (e: Exception) {
                error = e.message
            }
        }
    }

    LaunchedEffect(api) {
        while (true) {
            refresh()
            delay(10_000)
        }
    }

    Column(Modifier = Modifier.fillMaxSize().padding(12.dp)) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(
                onClick = {
                    scope.launch {
                        scanning = true
                        try {
                            api.runCycle()
                            refresh()
                        } catch (e: Exception) {
                            error = e.message
                        } finally {
                            scanning = false
                        }
                    }
                },
                enabled = !scanning,
                colors = ButtonDefaults.buttonColors(containerColor = Blue)
            ) { Text(if (scanning) "Scanning…" else "Run scan") }

            Row(
                Modifier
                    .background(if (autoTrade) Green.copy(alpha = 0.15f) else Card, RoundedCornerShape(8.dp))
                    .padding(horizontal = 10.dp, vertical = 6.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text("Auto demo", color = TextMain, fontSize = 12.sp)
                Switch(checked = autoTrade, onCheckedChange = onToggleAuto)
            }
        }

        if (error != null) Text(error!!, color = Rose, fontSize = 12.sp, modifier = Modifier.padding(top = 8.dp))

        Spacer(Modifier = Modifier.height(8.dp))

        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp), modifier = Modifier.weight(1f)) {
            items(items, key = { it.id }) { opp ->
                OppRow(opp, selected?.id == opp.id) { selected = opp }
            }
        }

        selected?.let { opp ->
            Spacer(Modifier = Modifier.height(8.dp))
            DetailCard(opp) {
                scope.launch {
                    try {
                        api.openTrade(opp.id)
                        refresh()
                    } catch (e: Exception) {
                        error = e.message
                    }
                }
            }
        }
    }
}

@Composable
fun OppRow(opp: Opportunity, selected: Boolean, onClick: () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(if (selected) Blue.copy(alpha = 0.15f) else Card, RoundedCornerShape(12.dp))
            .clickable { onClick() }
            .padding(12.dp)
    ) {
        Row(Modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
            Column {
                Text(opp.symbol, color = TextMain, fontWeight = FontWeight.SemiBold)
                Text(opp.best_match?.pattern_name ?: "—", color = TextDim, fontSize = 11.sp)
            }
            Column(horizontalAlignment = Alignment.End) {
                Text(opp.trade?.side ?: "—", color = if (opp.trade?.side == "BUY") Green else Rose, fontSize = 12.sp)
                Text(opp.decision?.action ?: "", color = when (opp.decision?.action) {
                    "APPROVE" -> Green
                    "WAIT" -> Amber
                    else -> TextDim
                }, fontSize = 11.sp)
            }
        }
        Spacer(Modifier = Modifier.height(4.dp))
        Text(
            "sim ${opp.best_match?.similarity?.toInt() ?: "—"}% · A ${opp.market_analysis?.score?.toInt() ?: "—"} · RR ${opp.trade?.risk_reward ?: "—"}",
            color = TextDim,
            fontSize = 11.sp
        )
    }
}

@Composable
fun DetailCard(opp: Opportunity, onOpen: () -> Unit) {
    Column(
        Modifier
            .fillMaxWidth()
            .background(Card, RoundedCornerShape(12.dp))
            .padding(12.dp)
    ) {
        Text(opp.decision?.reason ?: "", color = TextMain, fontSize = 12.sp)
        Spacer(Modifier = Modifier.height(6.dp))
        Text(
            "Entry ${opp.trade?.entry} · SL ${opp.trade?.stop_loss} · TP1 ${opp.trade?.take_profit_1}",
            color = TextDim,
            fontSize = 11.sp
        )
        if (opp.decision?.action == "APPROVE" && opp.status != "traded") {
            Spacer(Modifier = Modifier.height(8.dp))
            Button(onClick = onOpen, colors = ButtonDefaults.buttonColors(containerColor = Green)) {
                Text("Open demo trade")
            }
        }
    }
}

@Composable
fun TradesScreen(api: XoraApi) {
    var positions by remember { mutableStateOf<List<Position>>(emptyList()) }
    var summary by remember { mutableStateOf<TradeSummary?>(null) }
    var error by remember { mutableStateOf<String?>(null) }
    val scope = rememberCoroutineScope()

    fun refresh() {
        scope.launch {
            try {
                positions = api.positions()
                summary = api.summary()
                error = null
            } catch (e: Exception) {
                error = e.message
            }
        }
    }

    LaunchedEffect(api) {
        while (true) {
            refresh()
            delay(10_000)
        }
    }

    Column(Modifier = Modifier.fillMaxSize().padding(12.dp)) {
        summary?.let { s ->
            Row(Modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                StatChip("Open", "${s.open_count}")
                StatChip("Closed", "${s.closed_count}")
                StatChip("Win%", "${s.win_rate}")
                StatChip("PnL", "${s.total_realized_pnl}")
            }
            Spacer(Modifier = Modifier.height(12.dp))
        }
        if (error != null) Text(error!!, color = Rose, fontSize = 12.sp)
        LazyColumn(verticalArrangement = Arrangement.spacedBy(8.dp)) {
            items(positions, key = { it.id }) { p ->
                Column(
                    Modifier
                        .fillMaxWidth()
                        .background(Card, RoundedCornerShape(12.dp))
                        .padding(12.dp)
                ) {
                    Row(Modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween) {
                        Text(p.symbol, color = TextMain, fontWeight = FontWeight.SemiBold)
                        Text(p.status ?: "", color = if (p.status == "open") Green else TextDim, fontSize = 12.sp)
                    }
                    Text(
                        "${p.side} · entry ${p.entry} · qty ${p.quantity} · ${p.leverage}x",
                        color = TextDim,
                        fontSize = 11.sp
                    )
                    if (p.realized_pnl != null) {
                        Text("PnL ${p.realized_pnl}", color = if ((p.realized_pnl ?: 0.0) >= 0) Green else Rose, fontSize = 12.sp)
                    }
                    if (p.status == "open") {
                        TextButton(onClick = {
                            scope.launch {
                                try {
                                    api.closeTrade(p.id)
                                    refresh()
                                } catch (e: Exception) {
                                    error = e.message
                                }
                            }
                        }) { Text("Close", color = Rose) }
                    }
                }
            }
        }
    }
}

@Composable
fun RowScope.StatChip(label: String, value: String) {
    Column(
        Modifier
            .weight(1f)
            .background(Card, RoundedCornerShape(10.dp))
            .padding(10.dp)
    ) {
        Text(label, color = TextDim, fontSize = 10.sp)
        Text(value, color = TextMain, fontWeight = FontWeight.SemiBold, fontSize = 13.sp)
    }
}
