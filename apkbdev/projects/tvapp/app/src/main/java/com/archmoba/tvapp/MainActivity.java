package com.archmoba.tvapp;

import android.app.Activity;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.res.Configuration;
import android.graphics.Bitmap;
import android.graphics.BitmapFactory;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.util.LruCache;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
import android.widget.ImageView;
import android.widget.LinearLayout;
import android.widget.ProgressBar;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.ArrayAdapter;
import android.widget.TextView;
import android.widget.Toast;

import androidx.media3.common.MediaItem;
import androidx.media3.common.MimeTypes;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.ui.PlayerView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** TVAPP Android: visor en la cabecera y catálogo IPTV-org. */
public final class MainActivity extends Activity {
    private static final int BG = Color.rgb(23, 24, 32);
    private static final int SIDE = Color.rgb(16, 17, 22);
    private static final int PANEL = Color.rgb(27, 28, 37);
    private static final int CARD = Color.rgb(41, 43, 56);
    private static final int CARD_ACTIVE = Color.rgb(32, 70, 80);
    private static final int CYAN = Color.rgb(108, 198, 215);
    private static final int GOLD = Color.rgb(246, 201, 94);
    private static final int TEXT = Color.rgb(246, 247, 249);
    private static final int MUTED = Color.rgb(162, 167, 182);
    private static final String IPTV = "https://iptv-org.github.io/iptv/";
    private static final int PAGE = 24;
    private static final String[] CATEGORIES = {
        "Todos", "Categorías", "Noticias", "Deportes", "Películas", "Música",
        "Países", "Idiomas", "Ecuador", "Español", "Infantil", "Cultura", "Favoritos"
    };
    private static final String[] NAV = {"Inicio", "Vivo", "VOD", "Partidos", "Cuenta"};
    private static final String[] NAV_ICONS = {"⌂", "▣", "▤", "♜", "♙"};
    private static final Pattern LOGO = Pattern.compile("tvg-logo=\"([^\"]*)\"");
    private static final Pattern GROUP = Pattern.compile("group-title=\"([^\"]*)\"");

    private final ExecutorService dataPool = Executors.newSingleThreadExecutor();
    private final ExecutorService imagePool = Executors.newFixedThreadPool(3);
    private final Map<String, List<Channel>> cache = new HashMap<>();
    private final LinkedHashMap<String, Channel> favorites = new LinkedHashMap<>();
    private final LruCache<String, Bitmap> logos = new LruCache<>(96);
    private final LinkedHashSet<String> requestedImages = new LinkedHashSet<>();
    private int requestToken = 0;
    private int page = 0;
    private String category = "Deportes";
    private String tab = "Vivo";
    private String query = "";
    private String group = "Todos";
    private String playingUrl = null;
    private boolean loaded = false;
    private boolean searchVisible = false;
    private boolean muted = false;
    private List<Channel> current = new ArrayList<>();
    private ExoPlayer player;
    private PlayerView playerView;
    private FrameLayout hero;
    private ImageView heroLogo;
    private TextView videoCaption;
    private TextView playerStatus;
    private LinearLayout videoActions;
    private LinearLayout categoryList;
    private LinearLayout channelList;
    private LinearLayout navBar;
    private LinearLayout groupContainer;
    private TextView titleView;
    private TextView hintView;
    private TextView pagingView;
    private EditText searchInput;
    private ProgressBar loadingBar;
    private TextView pagePrev;
    private TextView pageNext;
    private Spinner groupSpinner;
    private boolean updatingSpinner = false;

    private static final class Channel {
        final String name, url, logo, group;
        Channel(String name, String url, String logo, String group) {
            this.name = name;
            this.url = url;
            this.logo = logo;
            this.group = group;
        }
    }

    private int dp(float value) {
        return Math.round(getResources().getDisplayMetrics().density * value);
    }

    private GradientDrawable rounded(int color, float radiusDp, int strokeColor) {
        GradientDrawable d = new GradientDrawable();
        d.setColor(color);
        d.setCornerRadius(dp(radiusDp));
        if (strokeColor != 0) d.setStroke(dp(1), strokeColor);
        return d;
    }

    private TextView label(String text, int sp, int color, boolean bold) {
        TextView view = new TextView(this);
        view.setText(text);
        view.setTextColor(color);
        view.setTextSize(sp);
        if (bold) view.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        view.setGravity(Gravity.CENTER_VERTICAL);
        view.setIncludeFontPadding(false);
        return view;
    }

    @Override public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        getWindow().setSoftInputMode(WindowManager.LayoutParams.SOFT_INPUT_ADJUST_RESIZE);
        loadFavorites();
        constructUi();
        switchCategory("Deportes");
    }

    private void constructUi() {
        FrameLayout frame = new FrameLayout(this);
        frame.setBackgroundColor(BG);
        LinearLayout body = new LinearLayout(this);
        body.setOrientation(LinearLayout.VERTICAL);
        body.setBackgroundColor(BG);
        frame.addView(body, new FrameLayout.LayoutParams(-1, -1));

        LinearLayout header = new LinearLayout(this);
        header.setGravity(Gravity.CENTER_VERTICAL);
        header.setPadding(dp(14), 0, dp(14), 0);
        header.setBackgroundColor(BG);
        body.addView(header, new LinearLayout.LayoutParams(-1, dp(70)));

        ImageView brand = new ImageView(this);
        brand.setImageResource(R.drawable.gdx_logo);
        brand.setScaleType(ImageView.ScaleType.FIT_CENTER);
        LinearLayout.LayoutParams brandParams = new LinearLayout.LayoutParams(dp(125), dp(58));
        header.addView(brand, brandParams);
        searchInput = new EditText(this);
        searchInput.setSingleLine(true);
        searchInput.setTextSize(13);
        searchInput.setHint("Buscar canales");
        searchInput.setHintTextColor(MUTED);
        searchInput.setTextColor(Color.WHITE);
        searchInput.setBackground(rounded(CARD, 12, 0));
        searchInput.setPadding(dp(9), 0, dp(9), 0);
        searchInput.setVisibility(View.GONE);
        LinearLayout.LayoutParams searchParams = new LinearLayout.LayoutParams(0, dp(37), 1);
        searchParams.leftMargin = dp(6);
        header.addView(searchInput, searchParams);
        searchInput.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) {
                query = s.toString().trim().toLowerCase(Locale.ROOT);
                page = 0;
                rebuildChannels();
            }
            @Override public void afterTextChanged(Editable s) {}
        });
        TextView search = label("⌕", 31, TEXT, false);
        search.setGravity(Gravity.CENTER);
        search.setBackground(rounded(0xFF333642, 30, 0xFF4A4C56));
        LinearLayout.LayoutParams searchButtonParams = new LinearLayout.LayoutParams(dp(42), dp(42));
        searchButtonParams.leftMargin = dp(7);
        header.addView(search, searchButtonParams);
        search.setOnClickListener(v -> {
            searchVisible = !searchVisible;
            searchInput.setVisibility(searchVisible ? View.VISIBLE : View.GONE);
            brand.setVisibility(searchVisible ? View.GONE : View.VISIBLE);
            if (!searchVisible) searchInput.setText("");
            else searchInput.requestFocus();
        });

        hero = new FrameLayout(this);
        hero.setBackgroundColor(0xFF11151B);
        body.addView(hero, new LinearLayout.LayoutParams(-1, dp(158)));
        heroLogo = new ImageView(this);
        heroLogo.setImageResource(R.drawable.gdx_logo);
        heroLogo.setScaleType(ImageView.ScaleType.FIT_CENTER);
        FrameLayout.LayoutParams logoP = new FrameLayout.LayoutParams(dp(190), dp(103), Gravity.CENTER);
        hero.addView(heroLogo, logoP);

        playerView = new PlayerView(this);
        playerView.setUseController(false);
        playerView.setVisibility(View.GONE);
        hero.addView(playerView, new FrameLayout.LayoutParams(-1, -1));
        playerStatus = label("", 11, TEXT, false);
        playerStatus.setGravity(Gravity.CENTER);
        playerStatus.setMaxLines(2);
        FrameLayout.LayoutParams ps = new FrameLayout.LayoutParams(-1, dp(42), Gravity.CENTER);
        ps.leftMargin = dp(16); ps.rightMargin = dp(16);
        hero.addView(playerStatus, ps);
        playerStatus.setVisibility(View.GONE);

        videoActions = new LinearLayout(this);
        videoActions.setGravity(Gravity.CENTER_VERTICAL);
        videoActions.setBackground(rounded(0xDD101924, 8, 0));
        videoActions.setPadding(dp(6), 0, dp(6), 0);
        FrameLayout.LayoutParams ctrl = new FrameLayout.LayoutParams(-1, dp(35), Gravity.BOTTOM);
        ctrl.bottomMargin = dp(2); ctrl.leftMargin = dp(2); ctrl.rightMargin = dp(2);
        hero.addView(videoActions, ctrl);
        videoActions.setVisibility(View.GONE);
        videoCaption = label("", 10, TEXT, true);
        videoCaption.setSingleLine(true);
        videoCaption.setEllipsize(android.text.TextUtils.TruncateAt.END);
        videoActions.addView(videoCaption, new LinearLayout.LayoutParams(0, -1, 1));
        smallButton(videoActions, "⏯", () -> togglePause());
        smallButton(videoActions, "♫", () -> toggleMute());
        smallButton(videoActions, "↗", () -> openExternal());
        smallButton(videoActions, "×", () -> stopPlayback());

        LinearLayout main = new LinearLayout(this);
        main.setOrientation(LinearLayout.HORIZONTAL);
        body.addView(main, new LinearLayout.LayoutParams(-1, 0, 1));
        ScrollView leftScroll = new ScrollView(this);
        leftScroll.setFillViewport(true);
        leftScroll.setVerticalScrollBarEnabled(false);
        leftScroll.setBackgroundColor(SIDE);
        categoryList = new LinearLayout(this);
        categoryList.setOrientation(LinearLayout.VERTICAL);
        categoryList.setPadding(dp(4), dp(12), dp(4), dp(102));
        leftScroll.addView(categoryList);
        main.addView(leftScroll, new LinearLayout.LayoutParams(dp(112), -1));

        LinearLayout right = new LinearLayout(this);
        right.setOrientation(LinearLayout.VERTICAL);
        right.setPadding(dp(6), dp(10), dp(7), dp(96));
        right.setBackgroundColor(PANEL);
        main.addView(right, new LinearLayout.LayoutParams(0, -1, 1));
        titleView = label("Deportes", 19, TEXT, true);
        right.addView(titleView, new LinearLayout.LayoutParams(-1, dp(29)));
        hintView = label("Preparando lista...", 10, MUTED, false);
        right.addView(hintView, new LinearLayout.LayoutParams(-1, dp(23)));
        loadingBar = new ProgressBar(this, null, android.R.attr.progressBarStyleHorizontal);
        loadingBar.setIndeterminate(true);
        right.addView(loadingBar, new LinearLayout.LayoutParams(-1, dp(3)));
        groupContainer = new LinearLayout(this);
        groupContainer.setVisibility(View.GONE);
        right.addView(groupContainer, new LinearLayout.LayoutParams(-1, dp(44)));
        groupSpinner = new Spinner(this);
        groupContainer.addView(groupSpinner, new LinearLayout.LayoutParams(-1, -1));
        groupSpinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener() {
            @Override public void onNothingSelected(android.widget.AdapterView<?> parent) {}
            @Override public void onItemSelected(android.widget.AdapterView<?> parent, View view, int position, long id) {
                if (updatingSpinner) return;
                Object selected = groupSpinner.getSelectedItem();
                String value = selected == null ? "Todos" : selected.toString();
                if (!group.equals(value)) { group = value; page = 0; rebuildChannels(); }
            }
        });
        ScrollView channelsScroll = new ScrollView(this);
        channelsScroll.setFillViewport(false);
        channelsScroll.setVerticalScrollBarEnabled(false);
        channelList = new LinearLayout(this);
        channelList.setOrientation(LinearLayout.VERTICAL);
        channelsScroll.addView(channelList);
        right.addView(channelsScroll, new LinearLayout.LayoutParams(-1, 0, 1));

        LinearLayout pager = new LinearLayout(this);
        pager.setGravity(Gravity.CENTER_VERTICAL);
        right.addView(pager, new LinearLayout.LayoutParams(-1, dp(30)));
        pagingView = label("", 10, MUTED, false);
        pager.addView(pagingView, new LinearLayout.LayoutParams(0, -1, 1));
        pagePrev = label("‹", 23, TEXT, true); pagePrev.setGravity(Gravity.CENTER);
        pagePrev.setBackground(rounded(CARD, 7, 0));
        pager.addView(pagePrev, new LinearLayout.LayoutParams(dp(33), dp(27)));
        pageNext = label("›", 23, TEXT, true); pageNext.setGravity(Gravity.CENTER);
        pageNext.setBackground(rounded(CARD, 7, 0));
        LinearLayout.LayoutParams nextParams = new LinearLayout.LayoutParams(dp(33), dp(27));
        nextParams.leftMargin = dp(6); pager.addView(pageNext, nextParams);
        pagePrev.setOnClickListener(v -> { if (page > 0) { page--; rebuildChannels(); channelsScroll.smoothScrollTo(0,0); } });
        pageNext.setOnClickListener(v -> { page++; rebuildChannels(); channelsScroll.smoothScrollTo(0,0); });

        navBar = new LinearLayout(this);
        navBar.setGravity(Gravity.CENTER);
        navBar.setPadding(dp(4), dp(4), dp(4), dp(4));
        navBar.setBackground(rounded(0xEE2C2E40, 31, 0xFF666A84));
        FrameLayout.LayoutParams navLayout = new FrameLayout.LayoutParams(-1, dp(71), Gravity.BOTTOM);
        navLayout.leftMargin = dp(10); navLayout.rightMargin = dp(10); navLayout.bottomMargin = dp(10);
        frame.addView(navBar, navLayout);
        setContentView(frame);
        rebuildCategories();
        rebuildNavigation();
    }

    private void smallButton(LinearLayout parent, String symbol, Runnable action) {
        TextView button = label(symbol, 16, TEXT, true);
        button.setGravity(Gravity.CENTER);
        LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(dp(31), dp(29));
        p.leftMargin = dp(2);
        button.setBackground(rounded(0xFF263342, 7, 0));
        parent.addView(button, p);
        button.setOnClickListener(v -> action.run());
    }

    private void rebuildCategories() {
        categoryList.removeAllViews();
        for (String key : CATEGORIES) {
            TextView text = label(key, 12, key.equals(category) ? CYAN : TEXT, key.equals(category));
            text.setGravity(Gravity.CENTER);
            text.setMaxLines(2);
            if (key.equals(category)) text.setBackground(rounded(0xFF225461, 11, 0));
            LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(-1, dp(47));
            p.bottomMargin = dp(4);
            categoryList.addView(text, p);
            text.setOnClickListener(v -> { tab = "Vivo"; switchCategory(key); rebuildNavigation(); });
        }
    }

    private void rebuildNavigation() {
        navBar.removeAllViews();
        for (int i = 0; i < NAV.length; i++) {
            String item = NAV[i];
            LinearLayout cell = new LinearLayout(this);
            cell.setOrientation(LinearLayout.VERTICAL);
            cell.setGravity(Gravity.CENTER);
            boolean active = item.equals(tab);
            if (active) cell.setBackground(rounded(0xFF2B5464, 22, 0));
            TextView icon = label(NAV_ICONS[i], 23, active ? CYAN : 0xFFC3C9D3, false);
            icon.setGravity(Gravity.CENTER);
            cell.addView(icon, new LinearLayout.LayoutParams(-1, dp(30)));
            TextView name = label(item, 10, active ? CYAN : 0xFFC3C9D3, active);
            name.setGravity(Gravity.CENTER);
            cell.addView(name, new LinearLayout.LayoutParams(-1, dp(19)));
            navBar.addView(cell, new LinearLayout.LayoutParams(0, -1, 1));
            cell.setOnClickListener(v -> {
                tab = item;
                String destination;
                switch (item) {
                    case "Inicio": destination = "Todos"; break;
                    case "VOD": destination = "Películas"; break;
                    case "Partidos": destination = "Deportes"; break;
                    case "Cuenta": destination = "Favoritos"; break;
                    default: destination = category; break;
                }
                switchCategory(destination);
                rebuildNavigation();
            });
        }
    }

    private static String source(String category) {
        switch (category) {
            case "Todos": return "index.m3u";
            case "Categorías": return "index.category.m3u";
            case "Noticias": return "categories/news.m3u";
            case "Deportes": return "categories/sports.m3u";
            case "Películas": return "categories/movies.m3u";
            case "Música": return "categories/music.m3u";
            case "Países": return "index.country.m3u";
            case "Idiomas": return "index.language.m3u";
            case "Ecuador": return "countries/ec.m3u";
            case "Español": return "languages/spa.m3u";
            case "Infantil": return "categories/kids.m3u";
            case "Cultura": return "categories/culture.m3u";
            default: return null;
        }
    }

    private void switchCategory(String chosen) {
        category = chosen;
        group = "Todos";
        query = "";
        searchInput.setText("");
        page = 0;
        rebuildCategories();
        titleView.setText(chosen);
        if ("Favoritos".equals(chosen)) {
            current = new ArrayList<>(favorites.values());
            loaded = true;
            loadingBar.setVisibility(View.GONE);
            hintView.setText(current.size() + " favoritos guardados");
            updateGroupSelector();
            rebuildChannels();
            return;
        }
        List<Channel> local = cache.get(chosen);
        if (local != null) {
            current = local;
            loaded = true;
            hintView.setText(local.size() + " canales (caché)");
            loadingBar.setVisibility(View.GONE);
            updateGroupSelector();
            rebuildChannels();
            return;
        }
        loaded = false;
        current = new ArrayList<>();
        hintView.setText("Descargando lista M3U...");
        loadingBar.setVisibility(View.VISIBLE);
        rebuildChannels();
        final int token = ++requestToken;
        final String path = source(chosen);
        dataPool.execute(() -> {
            try {
                List<Channel> channels = downloadM3u(IPTV + path);
                runOnUiThread(() -> {
                    cache.put(chosen, channels);
                    if (isFinishing() || token != requestToken || !chosen.equals(category)) return;
                    current = channels;
                    loaded = true;
                    hintView.setText(channels.size() + " canales");
                    loadingBar.setVisibility(View.GONE);
                    updateGroupSelector();
                    rebuildChannels();
                });
            } catch (Exception ex) {
                runOnUiThread(() -> {
                    if (isFinishing() || token != requestToken || !chosen.equals(category)) return;
                    loaded = true;
                    loadingBar.setVisibility(View.GONE);
                    hintView.setText("Error al cargar: " + ex.getMessage());
                    rebuildChannels();
                });
            }
        });
    }

    private static String attribute(Pattern pattern, String s) {
        Matcher m = pattern.matcher(s);
        return m.find() ? m.group(1).trim() : "";
    }

    private static String afterExtinfComma(String line) {
        boolean quoted = false;
        int comma = -1;
        for (int i = 0; i < line.length(); i++) {
            char c = line.charAt(i);
            if (c == '"') quoted = !quoted;
            if (c == ',' && !quoted) comma = i;
        }
        return comma < 0 ? "" : line.substring(comma + 1).trim();
    }

    private static List<Channel> downloadM3u(String link) throws Exception {
        HttpURLConnection c = (HttpURLConnection) new URL(link).openConnection();
        c.setConnectTimeout(12000);
        c.setReadTimeout(20000);
        c.setRequestProperty("User-Agent", "ARCHMOBA-TVAPP-Android/0.1");
        c.setRequestProperty("Accept", "text/plain,*/*");
        c.setInstanceFollowRedirects(true);
        try {
            int status = c.getResponseCode();
            if (status < 200 || status > 299) throw new IllegalStateException("HTTP " + status);
            List<Channel> all = new ArrayList<>();
            try (InputStream stream = c.getInputStream();
                 BufferedReader in = new BufferedReader(new InputStreamReader(stream, StandardCharsets.UTF_8))) {
                String line;
                String name = "", logo = "", group = "";
                long bytes = 0;
                while ((line = in.readLine()) != null) {
                    bytes += line.length() * 2L;
                    if (bytes > 45_000_000L) throw new IllegalStateException("Lista M3U demasiado grande");
                    line = line.trim();
                    if (line.startsWith("#EXTINF:")) {
                        name = afterExtinfComma(line);
                        logo = attribute(LOGO, line);
                        group = attribute(GROUP, line);
                    } else if (line.startsWith("#EXTGRP:")) {
                        group = line.substring(8).trim();
                    } else if (!line.startsWith("#") && !line.isEmpty()) {
                        if (line.startsWith("http://") || line.startsWith("https://")) {
                            if (name.isEmpty()) name = "Canal " + (all.size() + 1);
                            all.add(new Channel(name, line, logo, group));
                            if (all.size() >= 40000) break;
                        }
                        name = ""; logo = ""; group = "";
                    }
                }
            }
            return all;
        } finally {
            c.disconnect();
        }
    }

    private void updateGroupSelector() {
        boolean grouped = "Categorías".equals(category) || "Países".equals(category) || "Idiomas".equals(category);
        if (!grouped) { groupContainer.setVisibility(View.GONE); return; }
        LinkedHashSet<String> unique = new LinkedHashSet<>();
        for (Channel ch : current) if (!ch.group.isEmpty()) unique.add(ch.group);
        ArrayList<String> values = new ArrayList<>(unique);
        Collections.sort(values, String.CASE_INSENSITIVE_ORDER);
        values.add(0, "Todos");
        updatingSpinner = true;
        ArrayAdapter<String> adapter = new ArrayAdapter<>(this, android.R.layout.simple_spinner_item, values);
        adapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        groupSpinner.setAdapter(adapter);
        groupSpinner.setSelection(0);
        updatingSpinner = false;
        groupContainer.setVisibility(View.VISIBLE);
    }

    private List<Channel> visible() {
        List<Channel> out = new ArrayList<>();
        for (Channel c : current) {
            if (!"Todos".equals(group) && !group.equals(c.group)) continue;
            if (!query.isEmpty() && !c.name.toLowerCase(Locale.ROOT).contains(query)) continue;
            out.add(c);
        }
        return out;
    }

    private void rebuildChannels() {
        if (channelList == null) return;
        channelList.removeAllViews();
        List<Channel> channels = visible();
        int totalPages = Math.max(1, (channels.size() + PAGE - 1) / PAGE);
        if (page >= totalPages) page = totalPages - 1;
        int start = page * PAGE;
        int end = Math.min(start + PAGE, channels.size());
        pagingView.setText(channels.isEmpty() ? "0 canales" : (start + 1) + "-" + end + " de " + channels.size());
        pagePrev.setAlpha(page == 0 ? .45f : 1f);
        pageNext.setAlpha(page >= totalPages - 1 ? .45f : 1f);
        if (channels.isEmpty()) {
            TextView noData = label(!loaded ? "Cargando canales..." : "Sin canales. Prueba otra categoría.", 12, MUTED, false);
            noData.setPadding(dp(4), dp(20), dp(3), 0);
            channelList.addView(noData);
            return;
        }
        for (int i = start; i < end; i++) addChannelCard(channels.get(i), (i - start) % 2 == 1);
    }

    private void addChannelCard(Channel ch, boolean highlighted) {
        LinearLayout card = new LinearLayout(this);
        card.setGravity(Gravity.CENTER_VERTICAL);
        card.setPadding(dp(4), dp(4), dp(4), dp(4));
        card.setBackground(rounded(highlighted ? CARD_ACTIVE : CARD, 12, 0));
        LinearLayout.LayoutParams outer = new LinearLayout.LayoutParams(-1, dp(68));
        outer.bottomMargin = dp(6);
        channelList.addView(card, outer);

        ImageView logo = new ImageView(this);
        logo.setScaleType(ImageView.ScaleType.FIT_CENTER);
        logo.setBackground(rounded(0xFF202633, 9, 0));
        card.addView(logo, new LinearLayout.LayoutParams(dp(42), dp(42)));
        loadChannelLogo(ch.logo, logo);
        LinearLayout lines = new LinearLayout(this);
        lines.setOrientation(LinearLayout.VERTICAL);
        lines.setGravity(Gravity.CENTER_VERTICAL);
        lines.setPadding(dp(6), 0, 0, 0);
        card.addView(lines, new LinearLayout.LayoutParams(0, -1, 1));
        TextView name = label(ch.name, 12, highlighted ? CYAN : TEXT, true);
        name.setSingleLine(true);
        name.setEllipsize(android.text.TextUtils.TruncateAt.END);
        lines.addView(name, new LinearLayout.LayoutParams(-1, dp(24)));
        TextView detail = label(ch.group.isEmpty() ? "Canal en vivo" : ch.group, 10, MUTED, false);
        detail.setSingleLine(true);
        detail.setEllipsize(android.text.TextUtils.TruncateAt.END);
        lines.addView(detail, new LinearLayout.LayoutParams(-1, dp(18)));
        TextView fav = label(favorites.containsKey(ch.url) ? "★" : "☆", 26,
                favorites.containsKey(ch.url) ? GOLD : MUTED, false);
        fav.setGravity(Gravity.CENTER);
        card.addView(fav, new LinearLayout.LayoutParams(dp(33), dp(50)));
        card.setOnClickListener(v -> play(ch));
        fav.setOnClickListener(v -> {
            if (favorites.containsKey(ch.url)) favorites.remove(ch.url);
            else favorites.put(ch.url, ch);
            saveFavorites();
            if ("Favoritos".equals(category)) current = new ArrayList<>(favorites.values());
            rebuildChannels();
        });
    }

    private void loadChannelLogo(String url, ImageView target) {
        if (url == null || !url.startsWith("https://") && !url.startsWith("http://")) {
            target.setImageResource(R.drawable.gdx_logo);
            return;
        }
        Bitmap existing = logos.get(url);
        if (existing != null) { target.setImageBitmap(existing); return; }
        target.setImageResource(R.drawable.gdx_logo);
        imagePool.execute(() -> {
            Bitmap bmp = null;
            HttpURLConnection conn = null;
            try {
                conn = (HttpURLConnection) new URL(url).openConnection();
                conn.setConnectTimeout(6500); conn.setReadTimeout(6500);
                conn.setRequestProperty("User-Agent", "ARCHMOBA-TVAPP-Android/0.1");
                if (conn.getResponseCode() == 200) {
                    try (InputStream in = conn.getInputStream()) {
                        ByteArrayOutputStream bytes = new ByteArrayOutputStream();
                        byte[] buffer = new byte[8192];
                        int n;
                        while ((n = in.read(buffer)) > 0 && bytes.size() < 400_000) bytes.write(buffer, 0, n);
                        byte[] data = bytes.toByteArray();
                        bmp = BitmapFactory.decodeByteArray(data, 0, data.length);
                    }
                }
            } catch (Exception ignored) {
            } finally {
                if (conn != null) conn.disconnect();
            }
            if (bmp != null) {
                Bitmap finalBmp = Bitmap.createScaledBitmap(bmp, dp(40), dp(40), true);
                logos.put(url, finalBmp);
                runOnUiThread(() -> { if (!isFinishing() && target.getParent() != null) target.setImageBitmap(finalBmp); });
            }
        });
    }

    private void play(Channel selected) {
        stopPlayback();
        playingUrl = selected.url;
        heroLogo.setVisibility(View.GONE);
        playerView.setVisibility(View.VISIBLE);
        playerStatus.setVisibility(View.VISIBLE);
        playerStatus.setText("Conectando transmisión...");
        videoCaption.setText(selected.name);
        videoActions.setVisibility(View.VISIBLE);
        try {
            player = new ExoPlayer.Builder(this).build();
            playerView.setPlayer(player);
            player.addListener(new Player.Listener() {
                @Override public void onPlaybackStateChanged(int state) {
                    if (state == Player.STATE_READY) playerStatus.setVisibility(View.GONE);
                    else if (state == Player.STATE_BUFFERING) {
                        playerStatus.setText("Cargando video...");
                        playerStatus.setVisibility(View.VISIBLE);
                    }
                }
                @Override public void onPlayerError(PlaybackException error) {
                    playerView.setVisibility(View.GONE);
                    heroLogo.setVisibility(View.VISIBLE);
                    playerStatus.setText("Canal no disponible. Abre VLC externo o elige otro.");
                    playerStatus.setVisibility(View.VISIBLE);
                }
            });
            MediaItem.Builder media = new MediaItem.Builder().setUri(Uri.parse(selected.url));
            if (selected.url.toLowerCase(Locale.ROOT).contains(".m3u8"))
                media.setMimeType(MimeTypes.APPLICATION_M3U8);
            player.setMediaItem(media.build());
            player.prepare();
            player.play();
        } catch (Exception error) {
            playerView.setVisibility(View.GONE);
            heroLogo.setVisibility(View.VISIBLE);
            playerStatus.setText("No se pudo abrir el canal: " + error.getMessage());
            playerStatus.setVisibility(View.VISIBLE);
        }
    }

    private void togglePause() {
        if (player != null) player.setPlayWhenReady(!player.getPlayWhenReady());
    }
    private void toggleMute() {
        muted = !muted;
        if (player != null) player.setVolume(muted ? 0f : 1f);
    }
    private void openExternal() {
        if (playingUrl == null) return;
        Intent intent = new Intent(Intent.ACTION_VIEW, Uri.parse(playingUrl));
        intent.addCategory(Intent.CATEGORY_BROWSABLE);
        try { startActivity(Intent.createChooser(intent, "Abrir transmisión con")); }
        catch (ActivityNotFoundException error) {
            Toast.makeText(this, "No se encontró un reproductor externo.", Toast.LENGTH_SHORT).show();
        }
    }
    private void stopPlayback() {
        if (player != null) {
            playerView.setPlayer(null);
            player.release();
            player = null;
        }
        playingUrl = null;
        heroLogo.setVisibility(View.VISIBLE);
        playerView.setVisibility(View.GONE);
        playerStatus.setVisibility(View.GONE);
        videoActions.setVisibility(View.GONE);
    }

    private void loadFavorites() {
        SharedPreferences p = getSharedPreferences("tvapp", MODE_PRIVATE);
        try {
            JSONArray items = new JSONArray(p.getString("fav_v1", "[]"));
            for (int i = 0; i < items.length(); i++) {
                JSONObject o = items.getJSONObject(i);
                String url = o.optString("url", "");
                if (url.startsWith("http://") || url.startsWith("https://")) {
                    Channel c = new Channel(o.optString("name", "Canal"), url,
                            o.optString("logo", ""), o.optString("group", ""));
                    favorites.put(url, c);
                }
            }
        } catch (Exception ignored) {}
    }
    private void saveFavorites() {
        JSONArray data = new JSONArray();
        try {
            for (Channel c : favorites.values()) {
                JSONObject obj = new JSONObject();
                obj.put("name", c.name); obj.put("url", c.url);
                obj.put("logo", c.logo); obj.put("group", c.group);
                data.put(obj);
            }
        } catch (Exception ignored) {}
        getSharedPreferences("tvapp", MODE_PRIVATE).edit().putString("fav_v1", data.toString()).apply();
    }

    @Override public void onDestroy() {
        stopPlayback();
        requestToken++;
        dataPool.shutdownNow();
        imagePool.shutdownNow();
        super.onDestroy();
    }

    @Override public void onBackPressed() {
        if (playingUrl != null) { stopPlayback(); return; }
        super.onBackPressed();
    }
}