package com.archmoba.mingatv;

import android.app.Activity;
import android.app.AlertDialog;
import android.content.SharedPreferences;
import android.content.pm.ActivityInfo;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.net.Uri;
import android.os.Bundle;
import android.text.Editable;
import android.text.TextWatcher;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowManager;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.EditText;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.TextView;

import androidx.media3.common.MediaItem;
import androidx.media3.common.MimeTypes;
import androidx.media3.common.PlaybackException;
import androidx.media3.common.Player;
import androidx.media3.datasource.DefaultHttpDataSource;
import androidx.media3.exoplayer.ExoPlayer;
import androidx.media3.exoplayer.source.DefaultMediaSourceFactory;
import androidx.media3.ui.PlayerView;

import org.json.JSONArray;
import org.json.JSONObject;

import java.text.Normalizer;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Random;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/** MINGA TV Android: interfaz nativa y reproductor Media3 HLS/IPTV. */
public final class MainActivity extends Activity {
    private static final int BG = Color.rgb(5, 6, 9);
    private static final int PANEL = Color.rgb(18, 20, 26);
    private static final int PANEL_LIGHT = Color.rgb(30, 34, 43);
    private static final int YELLOW = Color.rgb(255, 208, 0);
    private static final int TEXT = Color.rgb(238, 242, 249);
    private static final int SECONDARY = Color.rgb(153, 167, 185);
    private static final String PREFS = "minga_tv_android";
    private static final int FAVORITES = 0;
    private static final int PROVIDERS = 1;
    private static final int CATEGORIES = 2;
    private static final int CHANNELS = 3;
    private static final int TRASH = 4;
    private static final String TRASH_ACTION = "__trash_action__";

    private final ExecutorService workers = Executors.newFixedThreadPool(3);
    private final List<MingaData.Provider> providers = new ArrayList<>();
    private final List<MingaData.Category> categories = new ArrayList<>();
    private final List<MingaData.Channel> channels = new ArrayList<>();
    private final LinkedHashMap<String, MingaData.Channel> favorites = new LinkedHashMap<>();
    private final LinkedHashMap<String, MingaData.Channel> trash = new LinkedHashMap<>();
    private final List<Object> visibleRows = new ArrayList<>();
    private final List<String> rowLabels = new ArrayList<>();

    private SharedPreferences prefs;
    private int screen = FAVORITES;
    private int loadId = 0;
    private boolean providersLoaded = false;
    private boolean initialFinished = false;
    private boolean autoplayAttempted = false;
    private boolean destroyed = false;
    private boolean muted = false;
    private boolean fullScreen = false;
    private boolean adultAcknowledged = false;
    private MingaData.Provider chosenProvider;
    private MingaData.Category chosenCategory;
    private MingaData.Channel playingChannel;
    private MingaData.Channel previewChannel;
    private MingaData.Channel lastPlayed;

    private LinearLayout root, appHeader, tabRow, browserPanel, controlBar;
    private FrameLayout videoFrame, miniFrame;
    private PlayerView videoView, miniView;
    private ExoPlayer mainPlayer, miniPlayer;
    private TextView titleView, nowView, statusView, favoritesTab, browseTab;
    private TextView muteButton, starButton, trashButton, fullButton;
    private Button backButton;
    private EditText search;
    private ListView list;
    private ArrayAdapter<String> adapter;

    @Override
    public void onCreate(Bundle state) {
        super.onCreate(state);
        getWindow().setStatusBarColor(BG);
        getWindow().setNavigationBarColor(BG);
        prefs = getSharedPreferences(PREFS, MODE_PRIVATE);
        readSaved();
        createUi();
        showFavorites();
        downloadProviders();
        if (prefs.getBoolean("initial_imported", false)) {
            initialFinished = true;
        } else {
            importInitialChannels();
        }
        maybeAutoplay();
    }

    private int dp(float value) {
        return Math.round(value * getResources().getDisplayMetrics().density);
    }

    private GradientDrawable background(int fill, int radius, int border) {
        GradientDrawable shape = new GradientDrawable();
        shape.setColor(fill);
        shape.setCornerRadius(dp(radius));
        if (border != 0) shape.setStroke(dp(1), border);
        return shape;
    }

    private TextView text(String value, int size, int color, boolean bold) {
        TextView result = new TextView(this);
        result.setText(value);
        result.setTextSize(size);
        result.setTextColor(color);
        result.setGravity(Gravity.CENTER_VERTICAL);
        if (bold) result.setTypeface(Typeface.DEFAULT, Typeface.BOLD);
        return result;
    }

    private TextView action(String label, Runnable listener) {
        TextView result = text(label, 19, TEXT, false);
        result.setGravity(Gravity.CENTER);
        result.setBackground(background(PANEL, 9, 0));
        result.setOnClickListener(view -> listener.run());
        return result;
    }

    private void createUi() {
        root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setBackgroundColor(BG);
        setContentView(root);

        appHeader = new LinearLayout(this);
        appHeader.setOrientation(LinearLayout.VERTICAL);
        appHeader.setPadding(dp(14), dp(10), dp(14), dp(7));
        titleView = text("MINGA TV", 23, YELLOW, true);
        appHeader.addView(titleView);
        TextView subtitle = text("Tu mundo de entretenimiento", 11, SECONDARY, false);
        appHeader.addView(subtitle);
        root.addView(appHeader, new LinearLayout.LayoutParams(-1, -2));

        videoFrame = new FrameLayout(this);
        videoFrame.setBackgroundColor(Color.BLACK);
        root.addView(videoFrame, new LinearLayout.LayoutParams(-1, dp(218)));
        videoView = new PlayerView(this);
        videoView.setUseController(false);
        videoView.setKeepScreenOn(true);
        videoFrame.addView(videoView, new FrameLayout.LayoutParams(-1, -1));

        miniFrame = new FrameLayout(this);
        miniFrame.setBackground(background(Color.BLACK, 4, YELLOW));
        FrameLayout.LayoutParams miniParams = new FrameLayout.LayoutParams(dp(124), dp(82));
        miniParams.gravity = Gravity.TOP | Gravity.START;
        miniParams.setMargins(dp(9), dp(9), 0, 0);
        videoFrame.addView(miniFrame, miniParams);
        miniView = new PlayerView(this);
        miniView.setUseController(false);
        FrameLayout.LayoutParams miniVideoParams = new FrameLayout.LayoutParams(-1, -1);
        miniVideoParams.setMargins(dp(2), dp(2), dp(2), dp(2));
        miniFrame.addView(miniView, miniVideoParams);
        TextView closeMini = text("×", 21, Color.WHITE, true);
        closeMini.setGravity(Gravity.CENTER);
        closeMini.setBackground(background(0xcc202020, 6, 0));
        FrameLayout.LayoutParams closeParams = new FrameLayout.LayoutParams(dp(27), dp(27));
        closeParams.gravity = Gravity.TOP | Gravity.END;
        miniFrame.addView(closeMini, closeParams);
        closeMini.setOnClickListener(v -> closePreview());
        miniFrame.setOnClickListener(v -> restorePreview());
        miniFrame.setVisibility(View.GONE);

        controlBar = new LinearLayout(this);
        controlBar.setOrientation(LinearLayout.HORIZONTAL);
        controlBar.setGravity(Gravity.CENTER_VERTICAL);
        controlBar.setPadding(dp(6), dp(5), dp(6), dp(5));
        nowView = text("Selecciona un canal", 12, TEXT, false);
        nowView.setSingleLine(true);
        nowView.setEllipsize(android.text.TextUtils.TruncateAt.END);
        controlBar.addView(nowView, new LinearLayout.LayoutParams(0, dp(39), 1));
        muteButton = action("♪", this::toggleMute);
        starButton = action("☆", this::toggleFavorite);
        trashButton = action("♻", this::toggleTrash);
        fullButton = action("⛶", this::toggleFullScreen);
        for (TextView button : new TextView[]{muteButton, starButton, trashButton, fullButton}) {
            LinearLayout.LayoutParams p = new LinearLayout.LayoutParams(dp(37), dp(39));
            p.setMargins(dp(2), 0, dp(2), 0);
            controlBar.addView(button, p);
        }
        root.addView(controlBar, new LinearLayout.LayoutParams(-1, -2));

        tabRow = new LinearLayout(this);
        tabRow.setOrientation(LinearLayout.HORIZONTAL);
        tabRow.setPadding(dp(10), dp(4), dp(10), dp(4));
        favoritesTab = text("Favoritos", 16, YELLOW, true);
        favoritesTab.setGravity(Gravity.CENTER);
        browseTab = text("Buscar", 16, TEXT, true);
        browseTab.setGravity(Gravity.CENTER);
        tabRow.addView(favoritesTab, new LinearLayout.LayoutParams(0, dp(44), 1));
        tabRow.addView(browseTab, new LinearLayout.LayoutParams(0, dp(44), 1));
        favoritesTab.setOnClickListener(view -> showFavorites());
        browseTab.setOnClickListener(view -> showProviders());
        root.addView(tabRow, new LinearLayout.LayoutParams(-1, -2));

        browserPanel = new LinearLayout(this);
        browserPanel.setOrientation(LinearLayout.VERTICAL);
        root.addView(browserPanel, new LinearLayout.LayoutParams(-1, 0, 1));
        LinearLayout searchRow = new LinearLayout(this);
        searchRow.setGravity(Gravity.CENTER_VERTICAL);
        searchRow.setPadding(dp(10), dp(4), dp(10), dp(6));

        backButton = new Button(this);
        backButton.setText("‹");
        backButton.setAllCaps(false);
        backButton.setTextSize(23);
        backButton.setTextColor(YELLOW);
        backButton.setBackground(background(PANEL, 7, 0));
        backButton.setOnClickListener(view -> navigateBack());
        searchRow.addView(backButton, new LinearLayout.LayoutParams(dp(42), dp(43)));

        search = new EditText(this);
        search.setSingleLine(true);
        search.setTextSize(14);
        search.setTextColor(TEXT);
        search.setHintTextColor(SECONDARY);
        search.setHint("Buscar canales o categorías...");
        search.setBackground(background(PANEL_LIGHT, 10, 0));
        search.setPadding(dp(13), 0, dp(10), 0);
        LinearLayout.LayoutParams searchParams = new LinearLayout.LayoutParams(0, dp(43), 1);
        searchParams.setMargins(dp(6), 0, dp(6), 0);
        searchRow.addView(search, searchParams);
        search.addTextChangedListener(new TextWatcher() {
            @Override public void beforeTextChanged(CharSequence s, int start, int count, int after) {}
            @Override public void onTextChanged(CharSequence s, int start, int before, int count) {
                renderRows();
            }
            @Override public void afterTextChanged(Editable value) {}
        });

        TextView reload = action("↻", this::reloadCurrent);
        searchRow.addView(reload, new LinearLayout.LayoutParams(dp(42), dp(43)));
        browserPanel.addView(searchRow, new LinearLayout.LayoutParams(-1, -2));

        list = new ListView(this);
        list.setDividerHeight(dp(1));
        list.setDivider(new android.graphics.drawable.ColorDrawable(PANEL_LIGHT));
        list.setCacheColorHint(BG);
        list.setBackgroundColor(BG);
        adapter = new ArrayAdapter<String>(this, android.R.layout.simple_list_item_1, rowLabels) {
            @Override public View getView(int index, View convertView, ViewGroup parent) {
                View view = super.getView(index, convertView, parent);
                TextView label = (TextView) view;
                label.setTextColor(TEXT);
                label.setTextSize(15);
                label.setMinHeight(dp(52));
                label.setGravity(Gravity.CENTER_VERTICAL);
                label.setPadding(dp(17), dp(7), dp(9), dp(7));
                Object item = index < visibleRows.size() ? visibleRows.get(index) : null;
                if (item instanceof MingaData.Channel) {
                    MingaData.Channel stream = (MingaData.Channel) item;
                    if (playingChannel != null && playingChannel.url.equals(stream.url))
                        label.setTextColor(YELLOW);
                }
                label.setBackgroundColor(BG);
                return view;
            }
        };
        list.setAdapter(adapter);
        list.setOnItemClickListener((parent, view, position, id) -> openRow(position));
        browserPanel.addView(list, new LinearLayout.LayoutParams(-1, 0, 1));

        statusView = text("Cargando MINGA TV...", 11, SECONDARY, false);
        statusView.setPadding(dp(13), dp(6), dp(13), dp(8));
        root.addView(statusView, new LinearLayout.LayoutParams(-1, -2));
        updateButtons();
    }

    private void setStatus(String value) {
        if (!destroyed) statusView.setText(value);
    }

    private static String normalize(String value) {
        return Normalizer.normalize(value.toLowerCase(Locale.ROOT),
                Normalizer.Form.NFD).replaceAll("\\p{M}+", "");
    }

    private void renderRows() {
        if (adapter == null) return;
        String filter = normalize(search == null ? "" : search.getText().toString().trim());
        List<Object> items = new ArrayList<>();
        switch (screen) {
            case FAVORITES: {
                List<MingaData.Channel> ordered = new ArrayList<>(favorites.values());
                ordered.sort(Comparator.comparing(s -> s.name.toLowerCase(Locale.ROOT)));
                items.addAll(ordered);
                break;
            }
            case PROVIDERS:
                items.addAll(providers);
                items.add(TRASH_ACTION);
                break;
            case CATEGORIES:
                items.addAll(categories);
                break;
            case CHANNELS: {
                List<MingaData.Channel> sorted = new ArrayList<>();
                for (MingaData.Channel item : channels)
                    if (!trash.containsKey(item.url)) sorted.add(item);
                sorted.sort(Comparator.comparing(
                        (MingaData.Channel s) -> !favorites.containsKey(s.url))
                        .thenComparing(s -> s.name.toLowerCase(Locale.ROOT)));
                items.addAll(sorted);
                break;
            }
            case TRASH:
                items.addAll(trash.values());
                break;
            default:
                break;
        }
        visibleRows.clear();
        rowLabels.clear();
        for (Object item : items) {
            String label = labelFor(item);
            if (!filter.isEmpty() && !normalize(label).contains(filter)) continue;
            visibleRows.add(item);
            rowLabels.add(label);
        }
        if (rowLabels.isEmpty()) {
            visibleRows.add(null);
            String message = "Sin resultados";
            if (screen == FAVORITES && filter.isEmpty()) message = "No tienes canales favoritos.";
            else if (screen == TRASH && filter.isEmpty()) message = "La Papelera está vacía.";
            else if (screen == PROVIDERS && !providersLoaded)
                message = "Cargando proveedores...";
            else if (screen == CATEGORIES && categories.isEmpty())
                message = "Cargando categorías...";
            else if (screen == CHANNELS && channels.isEmpty())
                message = "Cargando canales...";
            rowLabels.add(message);
        }
        adapter.notifyDataSetChanged();
        if (backButton != null) backButton.setVisibility(
                screen == FAVORITES || screen == PROVIDERS ? View.GONE : View.VISIBLE);
        if (favoritesTab != null) favoritesTab.setTextColor(screen == FAVORITES ? YELLOW : TEXT);
        if (browseTab != null) browseTab.setTextColor(screen != FAVORITES ? YELLOW : TEXT);
    }

    private String labelFor(Object item) {
        if (item instanceof MingaData.Provider) {
            MingaData.Provider p = (MingaData.Provider) item;
            return "▣  " + p.name;
        }
        if (item instanceof MingaData.Category)
            return "▤  " + ((MingaData.Category) item).name;
        if (item instanceof MingaData.Channel) {
            MingaData.Channel c = (MingaData.Channel) item;
            return (playingChannel != null && playingChannel.url.equals(c.url) ? "▶  " : "   ")
                    + c.name;
        }
        if (TRASH_ACTION.equals(item)) return "♻  Papelera";
        return "";
    }

    private void clearSearch() {
        if (search != null && search.length() != 0) search.setText("");
    }

    private void showFavorites() {
        screen = FAVORITES;
        chosenProvider = null;
        chosenCategory = null;
        ++loadId;
        clearSearch();
        renderRows();
        setStatus("Favoritos guardados: " + favorites.size());
    }

    private void showProviders() {
        screen = PROVIDERS;
        chosenProvider = null;
        chosenCategory = null;
        ++loadId;
        clearSearch();
        renderRows();
        setStatus(providersLoaded
                ? "Selecciona un proveedor."
                : "Cargando proveedores de MINGA TV...");
    }

    private void navigateBack() {
        if (fullScreen) {
            toggleFullScreen();
            return;
        }
        if (screen == CHANNELS) {
            ++loadId;
            screen = CATEGORIES;
            chosenCategory = null;
            clearSearch();
            renderRows();
        } else if (screen == CATEGORIES || screen == TRASH) {
            showProviders();
        } else if (screen == PROVIDERS) {
            showFavorites();
        }
    }

    @Override
    public void onBackPressed() {
        if (fullScreen || screen != FAVORITES) navigateBack();
        else super.onBackPressed();
    }

    private void openRow(int index) {
        if (index >= visibleRows.size()) return;
        Object selected = visibleRows.get(index);
        if (selected instanceof MingaData.Provider) {
            MingaData.Provider provider = (MingaData.Provider) selected;
            if ((provider.id.equalsIgnoreCase("adultos")
                    || provider.name.contains("18+")) && !adultAcknowledged) {
                new AlertDialog.Builder(this)
                        .setTitle("Contenido para mayores de 18 años")
                        .setMessage("Este proveedor contiene canales para adultos. ¿Deseas continuar?")
                        .setNegativeButton("Cancelar", null)
                        .setPositiveButton("Continuar", (dialog, which) -> {
                            adultAcknowledged = true;
                            openProvider(provider);
                        }).show();
            } else openProvider(provider);
        } else if (selected instanceof MingaData.Category) {
            openCategory((MingaData.Category) selected);
        } else if (selected instanceof MingaData.Channel) {
            play((MingaData.Channel) selected);
        } else if (TRASH_ACTION.equals(selected)) {
            screen = TRASH;
            clearSearch();
            renderRows();
            setStatus("Papelera: selecciona un canal o restáuralo desde el botón ♻.");
        }
    }

    private void reloadCurrent() {
        if (screen == PROVIDERS) downloadProviders();
        else if (screen == CATEGORIES && chosenProvider != null) openProvider(chosenProvider);
        else if (screen == CHANNELS && chosenCategory != null) openCategory(chosenCategory);
        else renderRows();
    }

    private void downloadProviders() {
        setStatus("Sincronizando providers.json...");
        workers.execute(() -> {
            String raw = null;
            List<MingaData.Provider> available = null;
            boolean offline = false;
            try {
                raw = MingaData.download(MingaData.PROVIDERS_URL, 512 * 1024);
                available = MingaData.decodeProviders(raw);
            } catch (Exception e) {
                offline = true;
                raw = prefs.getString("providers_cache_raw", "");
                try {
                    available = MingaData.decodeProviders(raw);
                } catch (Exception ignored) {}
            }
            List<MingaData.Provider> result = available;
            String encryptedRaw = raw;
            boolean usedCache = offline;
            runOnUiThread(() -> {
                if (destroyed) return;
                if (result != null) {
                    providers.clear();
                    providers.addAll(result);
                    if (!usedCache) prefs.edit()
                            .putString("providers_cache_raw", encryptedRaw).apply();
                    providersLoaded = true;
                    setStatus(usedCache ? "Proveedores cargados desde copia local."
                            : "Proveedores actualizados desde GitHub.");
                } else {
                    providersLoaded = true;
                    setStatus("No se pudieron leer los proveedores. Usa ↻ para reintentar.");
                }
                if (screen == PROVIDERS) renderRows();
                maybeAutoplay();
            });
        });
    }

    private void openProvider(MingaData.Provider provider) {
        chosenProvider = provider;
        chosenCategory = null;
        screen = CATEGORIES;
        categories.clear();
        channels.clear();
        clearSearch();
        renderRows();
        setStatus("Cargando categorías de " + provider.name + "...");
        int generation = ++loadId;
        workers.execute(() -> {
            List<MingaData.Category> result = null;
            try {
                result = MingaData.categories(provider);
            } catch (Exception ignored) {}
            final List<MingaData.Category> categoriesResult = result;
            runOnUiThread(() -> {
                if (destroyed || generation != loadId || screen != CATEGORIES) return;
                categories.clear();
                if (categoriesResult == null) {
                    setStatus("No se pudieron cargar las categorías de este proveedor.");
                } else {
                    categories.addAll(categoriesResult);
                    setStatus(provider.name + " · " + categories.size() + " categorías.");
                }
                renderRows();
            });
        });
    }

    private void openCategory(MingaData.Category category) {
        if (chosenProvider == null) return;
        chosenCategory = category;
        screen = CHANNELS;
        channels.clear();
        clearSearch();
        renderRows();
        setStatus("Cargando canales de " + category.name + "...");
        int generation = ++loadId;
        MingaData.Provider provider = chosenProvider;
        workers.execute(() -> {
            List<MingaData.Channel> result = null;
            try {
                result = MingaData.channels(provider, category);
            } catch (Exception ignored) {}
            List<MingaData.Channel> loaded = result;
            runOnUiThread(() -> {
                if (destroyed || generation != loadId || screen != CHANNELS) return;
                channels.clear();
                if (loaded == null) {
                    setStatus("No se pudieron cargar los canales. Comprueba el servidor.");
                } else {
                    channels.addAll(loaded);
                    setStatus(category.name + " · " + channels.size() + " canales.");
                }
                renderRows();
            });
        });
    }

    private void readSaved() {
        readCollection(prefs.getString("favorites", "[]"), favorites);
        readCollection(prefs.getString("trash", "[]"), trash);
        for (String key : trash.keySet()) favorites.remove(key);
        try {
            lastPlayed = MingaData.Channel.fromJson(
                    new JSONObject(prefs.getString("last_played", "{}")));
            if (lastPlayed != null && trash.containsKey(lastPlayed.url))
                lastPlayed = null;
        } catch (Exception ignored) {}
    }

    private void readCollection(String raw, Map<String, MingaData.Channel> target) {
        try {
            JSONArray json = new JSONArray(raw);
            for (int i = 0; i < json.length(); i++) {
                MingaData.Channel channel = MingaData.Channel.fromJson(json.optJSONObject(i));
                if (channel != null) target.put(channel.url, channel);
            }
        } catch (Exception ignored) {}
    }

    private String collectionJson(Map<String, MingaData.Channel> source) {
        JSONArray array = new JSONArray();
        for (MingaData.Channel value : source.values()) array.put(value.toJson());
        return array.toString();
    }

    private void saveCollections() {
        prefs.edit()
                .putString("favorites", collectionJson(favorites))
                .putString("trash", collectionJson(trash)).apply();
    }

    private void importInitialChannels() {
        workers.execute(() -> {
            List<MingaData.Channel> imported = new ArrayList<>();
            try {
                JSONObject json = new JSONObject(MingaData.download(
                        MingaData.INITIAL_URL, 512 * 1024));
                JSONArray items = json.optJSONArray("channels");
                if (items != null) for (int i = 0; i < items.length(); i++) {
                    MingaData.Channel channel = MingaData.Channel.fromJson(items.optJSONObject(i));
                    if (channel != null) imported.add(channel);
                }
            } catch (Exception ignored) {}
            runOnUiThread(() -> {
                if (destroyed) return;
                if (!prefs.getBoolean("initial_imported", false)) {
                    for (MingaData.Channel c : imported)
                        if (!trash.containsKey(c.url)) favorites.put(c.url, c);
                    saveCollections();
                    if (!imported.isEmpty())
                        prefs.edit().putBoolean("initial_imported", true).apply();
                }
                initialFinished = true;
                if (screen == FAVORITES) renderRows();
                maybeAutoplay();
            });
        });
    }

    private void maybeAutoplay() {
        if (!providersLoaded || !initialFinished || autoplayAttempted || destroyed) return;
        autoplayAttempted = true;
        if (playingChannel != null) return;
        if (lastPlayed != null && !trash.containsKey(lastPlayed.url)) {
            play(lastPlayed);
        } else if (!favorites.isEmpty()) {
            List<MingaData.Channel> choices = new ArrayList<>(favorites.values());
            play(choices.get(new Random().nextInt(choices.size())));
        }
    }

    private ExoPlayer newPlayer() {
        DefaultHttpDataSource.Factory data = new DefaultHttpDataSource.Factory()
                .setUserAgent("MINGA-TV-Android/1.0")
                .setAllowCrossProtocolRedirects(true);
        return new ExoPlayer.Builder(this)
                .setMediaSourceFactory(new DefaultMediaSourceFactory(data))
                .build();
    }

    private void play(MingaData.Channel channel) {
        if (channel == null || (playingChannel != null
                && playingChannel.url.equals(channel.url))) return;
        String realUrl;
        try {
            realUrl = MingaData.resolveStream(channel, providers);
        } catch (Exception e) {
            setStatus("No se pudo abrir el canal: proveedor no disponible.");
            return;
        }
        if (mainPlayer != null) {
            closePreview();
            miniPlayer = mainPlayer;
            previewChannel = playingChannel;
            videoView.setPlayer(null);
            miniView.setPlayer(miniPlayer);
            miniPlayer.setVolume(0f);
            miniFrame.setVisibility(View.VISIBLE);
        }
        ExoPlayer created = newPlayer();
        mainPlayer = created;
        playingChannel = channel;
        videoView.setPlayer(created);
        created.setVolume(muted ? 0f : 1f);
        created.addListener(new Player.Listener() {
            @Override public void onPlaybackStateChanged(int state) {
                if (created != mainPlayer || destroyed) return;
                if (state == Player.STATE_READY) {
                    lastPlayed = channel;
                    prefs.edit().putString("last_played", channel.toJson().toString()).apply();
                    setStatus("Reproduciendo: " + channel.name);
                } else if (state == Player.STATE_BUFFERING) {
                    setStatus("Conectando a " + channel.name + "...");
                }
            }
            @Override public void onPlayerError(PlaybackException error) {
                if (created == mainPlayer && !destroyed) {
                    setStatus("No se pudo reproducir este canal. Prueba otro enlace.");
                }
            }
        });
        MediaItem.Builder item = new MediaItem.Builder().setUri(Uri.parse(realUrl));
        String mediaPath = Uri.parse(realUrl).getPath();
        if (mediaPath != null && mediaPath.toLowerCase(Locale.ROOT).endsWith(".m3u8"))
            item.setMimeType(MimeTypes.APPLICATION_M3U8);
        created.setMediaItem(item.build());
        created.prepare();
        created.play();
        nowView.setText("▶  " + channel.name);
        updateButtons();
        renderRows();
    }

    private void closePreview() {
        miniView.setPlayer(null);
        if (miniPlayer != null) {
            miniPlayer.release();
            miniPlayer = null;
        }
        previewChannel = null;
        miniFrame.setVisibility(View.GONE);
    }

    private void restorePreview() {
        if (miniPlayer == null || previewChannel == null) return;
        if (mainPlayer != null) {
            videoView.setPlayer(null);
            mainPlayer.release();
        }
        mainPlayer = miniPlayer;
        playingChannel = previewChannel;
        miniPlayer = null;
        previewChannel = null;
        miniView.setPlayer(null);
        miniFrame.setVisibility(View.GONE);
        videoView.setPlayer(mainPlayer);
        mainPlayer.setVolume(muted ? 0f : 1f);
        nowView.setText("▶  " + playingChannel.name);
        updateButtons();
        renderRows();
    }

    private void toggleMute() {
        muted = !muted;
        if (mainPlayer != null) mainPlayer.setVolume(muted ? 0f : 1f);
        updateButtons();
    }

    private void toggleFavorite() {
        if (playingChannel == null) return;
        String url = playingChannel.url;
        if (favorites.containsKey(url)) favorites.remove(url);
        else {
            trash.remove(url);
            favorites.put(url, playingChannel);
        }
        saveCollections();
        updateButtons();
        renderRows();
    }

    private void toggleTrash() {
        if (playingChannel == null) return;
        String url = playingChannel.url;
        if (trash.containsKey(url)) trash.remove(url);
        else {
            favorites.remove(url);
            trash.put(url, playingChannel);
            if (lastPlayed != null && url.equals(lastPlayed.url)) {
                lastPlayed = null;
                prefs.edit().remove("last_played").apply();
            }
        }
        saveCollections();
        updateButtons();
        renderRows();
    }

    private void updateButtons() {
        if (muteButton == null) return;
        muteButton.setText(muted ? "🔇" : "♪");
        if (playingChannel == null) {
            starButton.setText("☆");
            trashButton.setText("♻");
            return;
        }
        starButton.setText(favorites.containsKey(playingChannel.url) ? "★" : "☆");
        trashButton.setText(trash.containsKey(playingChannel.url) ? "↩" : "♻");
    }

    private void toggleFullScreen() {
        fullScreen = !fullScreen;
        if (fullScreen) {
            appHeader.setVisibility(View.GONE);
            tabRow.setVisibility(View.GONE);
            browserPanel.setVisibility(View.GONE);
            statusView.setVisibility(View.GONE);
            videoFrame.setLayoutParams(new LinearLayout.LayoutParams(-1, 0, 1));
            getWindow().addFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
            setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_SENSOR_LANDSCAPE);
            fullButton.setText("⤢");
        } else {
            videoFrame.setLayoutParams(new LinearLayout.LayoutParams(-1, dp(218)));
            appHeader.setVisibility(View.VISIBLE);
            tabRow.setVisibility(View.VISIBLE);
            browserPanel.setVisibility(View.VISIBLE);
            statusView.setVisibility(View.VISIBLE);
            getWindow().clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
            setRequestedOrientation(ActivityInfo.SCREEN_ORIENTATION_UNSPECIFIED);
            fullButton.setText("⛶");
        }
    }

    @Override
    public void onConfigurationChanged(Configuration newConfig) {
        super.onConfigurationChanged(newConfig);
    }

    @Override
    protected void onStop() {
        super.onStop();
        if (mainPlayer != null) mainPlayer.pause();
        if (miniPlayer != null) miniPlayer.pause();
    }

    @Override
    protected void onDestroy() {
        destroyed = true;
        ++loadId;
        closePreview();
        if (mainPlayer != null) {
            videoView.setPlayer(null);
            mainPlayer.release();
            mainPlayer = null;
        }
        workers.shutdownNow();
        super.onDestroy();
    }
}
