package com.archmoba.mingatv;

import org.json.JSONArray;
import org.json.JSONObject;

import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Catalogos remotos, canales y referencias virtuales de MINGA TV. */
final class MingaData {
    static final String RAW_BASE =
            "https://raw.githubusercontent.com/mobatfb/archmoba-dev/main/TVAPP";
    static final String PROVIDERS_URL = RAW_BASE + "/providers.json";
    static final String INITIAL_URL = RAW_BASE + "/initial.json";
    static final int MAX_M3U = 35 * 1024 * 1024;

    private MingaData() {}

    static final class Provider {
        final String id, name, server, username, password, error;

        Provider(String id, String name, String server, String username,
                 String password, String error) {
            this.id = id;
            this.name = name;
            this.server = server;
            this.username = username;
            this.password = password;
            this.error = error;
        }

        String kind() {
            if (!error.isEmpty()) return "invalid";
            if (server.isEmpty()) return "missing";
            String path;
            try {
                path = new URL(server).getPath().toLowerCase(Locale.ROOT);
            } catch (Exception e) {
                return "invalid";
            }
            if (path.endsWith(".json")) return "json";
            if (path.endsWith(".m3u")) return "m3u";
            if (path.endsWith(".m3u8")) return "stream";
            if (!username.isEmpty() && !password.isEmpty()) return "xtream";
            return "unsupported";
        }
    }

    static final class Channel {
        final String name, url, group;
        final JSONObject headers;

        Channel(String name, String url, String group, JSONObject headers) {
            this.name = name;
            this.url = url;
            this.group = group;
            this.headers = headers == null ? new JSONObject() : headers;
        }

        JSONObject toJson() {
            JSONObject data = new JSONObject();
            try {
                data.put("name", name);
                data.put("url", url);
                data.put("group", group);
                data.put("headers", headers);
            } catch (Exception ignored) {}
            return data;
        }

        static Channel fromJson(JSONObject json) {
            if (json == null) return null;
            String name = json.optString("name", "").trim();
            String url = json.optString("url", "").trim();
            if (name.isEmpty() || !isChannelUrl(url)) return null;
            String group = json.optString("group", "General");
            return new Channel(name, url, group, json.optJSONObject("headers"));
        }
    }

    static final class Category {
        final String name, url, kind, categoryId;
        final List<Channel> inline;

        Category(String name, String url, String kind,
                 String categoryId, List<Channel> inline) {
            this.name = name;
            this.url = url;
            this.kind = kind;
            this.categoryId = categoryId;
            this.inline = inline;
        }
    }

    static boolean isChannelUrl(String url) {
        return url.startsWith("https://") || url.startsWith("http://")
                || url.startsWith("xtream://");
    }

    static String download(String url, int maxBytes) throws Exception {
        HttpURLConnection conn = (HttpURLConnection) new URL(url).openConnection();
        conn.setRequestMethod("GET");
        conn.setRequestProperty("User-Agent", "MINGA-TV-Android/1.0");
        conn.setRequestProperty("Cache-Control", "no-cache");
        conn.setConnectTimeout(12000);
        conn.setReadTimeout(18000);
        conn.setInstanceFollowRedirects(true);
        try {
            int status = conn.getResponseCode();
            if (status < 200 || status >= 300)
                throw new IllegalStateException("Respuesta del servidor no disponible.");
            try (InputStream input = conn.getInputStream();
                 ByteArrayOutputStream output = new ByteArrayOutputStream()) {
                byte[] buffer = new byte[16384];
                int count;
                while ((count = input.read(buffer)) != -1) {
                    if (output.size() + count > maxBytes)
                        throw new IllegalArgumentException("Catalogo demasiado grande.");
                    output.write(buffer, 0, count);
                }
                return output.toString(StandardCharsets.UTF_8.name());
            }
        } finally {
            conn.disconnect();
        }
    }

    static List<Provider> decodeProviders(String jsonText) throws Exception {
        JSONObject root = new JSONObject(jsonText);
        JSONArray items = root.getJSONArray("providers");
        List<Provider> result = new ArrayList<>();
        Set<String> ids = new HashSet<>();
        for (int i = 0; i < items.length(); i++) {
            JSONObject raw = items.optJSONObject(i);
            if (raw == null) continue;
            String id = raw.optString("id", "").trim();
            if (!id.matches("[A-Za-z0-9_-]{1,64}") || !ids.add(id)) continue;
            String name = raw.optString("name", "Proveedor " + (i + 1));
            try {
                name = CipherUtil.decrypt(name).trim();
                String server = CipherUtil.decrypt(raw.optString("server", "")).trim();
                String username = CipherUtil.decrypt(raw.optString("username", ""));
                String password = CipherUtil.decrypt(raw.optString("password", ""));
                if (name.isEmpty() || (!server.isEmpty() &&
                        !(server.startsWith("https://") || server.startsWith("http://"))))
                    throw new IllegalArgumentException("Proveedor incorrecto");
                result.add(new Provider(id, name, server, username, password, ""));
            } catch (Exception e) {
                if (name.startsWith("encv1:")) name = "Proveedor " + (i + 1);
                result.add(new Provider(id, name, "", "", "",
                        "No se pudieron descifrar los datos del proveedor."));
            }
        }
        if (result.isEmpty()) throw new IllegalArgumentException("No hay proveedores.");
        return result;
    }

    static List<Category> categories(Provider provider) throws Exception {
        switch (provider.kind()) {
            case "json":
                return parseJsonCatalog(provider,
                        download(provider.server, 3 * 1024 * 1024));
            case "m3u": {
                List<Category> one = new ArrayList<>();
                one.add(new Category("Todos", provider.server, "m3u", "", null));
                return one;
            }
            case "stream": {
                List<Category> one = new ArrayList<>();
                List<Channel> channels = new ArrayList<>();
                channels.add(new Channel(provider.name, provider.server,
                        provider.name, null));
                one.add(new Category("Todos", "inline://" + provider.id + "/0",
                        "inline", "", channels));
                return one;
            }
            case "xtream":
                return xtreamCategories(provider);
            case "missing":
                throw new IllegalStateException("Este proveedor no tiene servidor configurado.");
            case "invalid":
                throw new IllegalStateException(provider.error);
            default:
                throw new IllegalStateException("Tipo de servidor no compatible.");
        }
    }

    private static List<Category> parseJsonCatalog(
            Provider provider, String text) throws Exception {
        JSONObject root = new JSONObject(text);
        List<Category> result = new ArrayList<>();
        JSONArray playlists = root.optJSONArray("playlists");
        if (playlists != null) {
            for (int i = 0; i < playlists.length(); i++) {
                JSONObject entry = playlists.optJSONObject(i);
                if (entry == null) continue;
                String name = entry.optString("name", "").trim();
                String url = entry.optString("url", "").trim();
                if (!name.isEmpty() && isChannelUrl(url)) {
                    result.add(new Category(name, url, "m3u", "", null));
                }
            }
        } else {
            JSONArray groups = root.optJSONArray("categories");
            if (groups == null) {
                groups = new JSONArray();
                JSONObject all = new JSONObject();
                all.put("name", "Todos");
                all.put("channels", root.optJSONArray("channels"));
                groups.put(all);
            }
            for (int i = 0; i < groups.length(); i++) {
                JSONObject entry = groups.optJSONObject(i);
                if (entry == null) continue;
                String name = entry.optString("name", "").trim();
                if (name.isEmpty()) continue;
                JSONArray items = entry.optJSONArray("channels");
                List<Channel> channels = new ArrayList<>();
                if (items != null) {
                    for (int j = 0; j < items.length(); j++) {
                        JSONObject value = items.optJSONObject(j);
                        if (value == null) continue;
                        String label = value.optString("name",
                                value.optString("tvg_name", "")).trim();
                        String url = value.optString("url", "").trim();
                        if (label.isEmpty() || !isChannelUrl(url)) continue;
                        channels.add(new Channel(label, url,
                                value.optString("group", name),
                                value.optJSONObject("headers")));
                    }
                }
                channels.sort(Comparator.comparing(
                        c -> c.name.toLowerCase(Locale.ROOT)));
                result.add(new Category(name,
                        "inline://" + provider.id + "/" + i, "inline", "", channels));
            }
        }
        if (result.isEmpty()) throw new IllegalStateException("Catalogo sin categorias.");
        result.sort(Comparator.comparing(c -> c.name.toLowerCase(Locale.ROOT)));
        return result;
    }

    private static String quote(String value) throws Exception {
        return URLEncoder.encode(value, StandardCharsets.UTF_8.name());
    }

    private static String xtreamApi(Provider provider, String action,
                                    String categoryId) throws Exception {
        String base = provider.server.trim();
        if (base.endsWith("/")) base = base.substring(0, base.length() - 1);
        if (!base.endsWith("/player_api.php")) base += "/player_api.php";
        String url = base + "?username=" + quote(provider.username)
                + "&password=" + quote(provider.password)
                + "&action=" + quote(action);
        if (categoryId != null) url += "&category_id=" + quote(categoryId);
        return url;
    }

    private static List<Category> xtreamCategories(Provider provider) throws Exception {
        JSONArray data = new JSONArray(download(
                xtreamApi(provider, "get_live_categories", null), 6 * 1024 * 1024));
        List<Category> result = new ArrayList<>();
        result.add(new Category("Todos",
                "xtream://" + provider.id + "/category/all", "xtream", null, null));
        for (int i = 0; i < data.length(); i++) {
            JSONObject category = data.optJSONObject(i);
            if (category == null) continue;
            String name = category.optString("category_name", "").trim();
            String id = category.optString("category_id", "");
            if (name.isEmpty() || !id.matches("[0-9]{1,20}")) continue;
            result.add(new Category(name,
                    "xtream://" + provider.id + "/category/" + id,
                    "xtream", id, null));
        }
        return result;
    }

    static List<Channel> channels(Provider provider, Category category) throws Exception {
        if ("inline".equals(category.kind)) {
            return new ArrayList<>(category.inline);
        }
        if ("m3u".equals(category.kind)) {
            return parseM3u(download(category.url, MAX_M3U), category.name);
        }
        if (!"xtream".equals(category.kind)) {
            throw new IllegalArgumentException("Formato de categoria desconocido.");
        }
        JSONArray array = new JSONArray(download(
                xtreamApi(provider, "get_live_streams", category.categoryId), MAX_M3U));
        List<Channel> result = new ArrayList<>();
        Set<String> seen = new HashSet<>();
        for (int i = 0; i < array.length(); i++) {
            JSONObject item = array.optJSONObject(i);
            if (item == null) continue;
            String name = item.optString("name", "").trim();
            String id = item.optString("stream_id", "");
            if (name.isEmpty() || !id.matches("[0-9]{1,20}")) continue;
            String extension = item.optString("container_extension", "ts").toLowerCase(Locale.ROOT);
            if (!extension.matches("ts|m3u8|mp4")) extension = "ts";
            String url = "xtream://" + provider.id + "/" + id + "." + extension;
            if (!seen.add(url)) continue;
            result.add(new Channel(name, url, category.name, null));
        }
        result.sort(Comparator.comparing(c -> c.name.toLowerCase(Locale.ROOT)));
        return result;
    }

    private static String attr(String line, String name) {
        Pattern pattern = Pattern.compile(
                Pattern.quote(name) + "=\"([^\"]*)\"", Pattern.CASE_INSENSITIVE);
        Matcher matcher = pattern.matcher(line);
        return matcher.find() ? matcher.group(1) : "";
    }

    static List<Channel> parseM3u(String text, String group) {
        if (!text.trim().startsWith("#EXTM3U"))
            throw new IllegalArgumentException("No es una lista M3U.");
        List<Channel> result = new ArrayList<>();
        String name = null;
        String channelGroup = group;
        for (String raw : text.split("\n")) {
            String line = raw.trim();
            if (line.startsWith("#EXTINF:")) {
                int comma = line.lastIndexOf(',');
                name = comma >= 0 ? line.substring(comma + 1).trim() : "";
                if (name.isEmpty()) name = attr(line, "tvg-name");
                if (name.isEmpty()) name = null;
                String groupTitle = attr(line, "group-title");
                channelGroup = groupTitle.isEmpty() ? group : groupTitle;
            } else if (name != null &&
                    (line.startsWith("http://") || line.startsWith("https://"))) {
                result.add(new Channel(name, line, channelGroup, null));
                name = null;
            }
        }
        result.sort(Comparator.comparing(c -> c.name.toLowerCase(Locale.ROOT)));
        return result;
    }

    static String resolveStream(Channel channel, List<Provider> providers) throws Exception {
        if (!channel.url.startsWith("xtream://")) return channel.url;
        String path = channel.url.substring("xtream://".length());
        int slash = path.indexOf('/');
        if (slash <= 0) throw new IllegalStateException("Canal premium incorrecto.");
        String providerId = path.substring(0, slash);
        String idAndExt = path.substring(slash + 1);
        if (!idAndExt.matches("[0-9]{1,20}\\.(ts|m3u8|mp4)"))
            throw new IllegalStateException("ID premium incorrecto.");
        Provider chosen = null;
        for (Provider p : providers) {
            if (p.id.equals(providerId)) {
                chosen = p;
                break;
            }
        }
        if (chosen == null || !"xtream".equals(chosen.kind()))
            throw new IllegalStateException("Proveedor premium no disponible.");
        String base = chosen.server;
        if (base.endsWith("/")) base = base.substring(0, base.length() - 1);
        if (base.endsWith("/player_api.php"))
            base = base.substring(0, base.length() - "/player_api.php".length());
        // Las credenciales solo se colocan en la URL de reproduccion en memoria.
        return base + "/live/" + quote(chosen.username) + "/"
                + quote(chosen.password) + "/" + idAndExt;
    }
}
