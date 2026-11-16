package com.shelf.pwa;

import android.Manifest;
import android.app.Activity;
import android.app.AlertDialog;
import android.content.Intent;
import android.content.SharedPreferences;
import android.content.pm.PackageManager;
import android.graphics.Color;
import android.os.Build;
import android.os.Bundle;
import android.util.Log;
import android.view.View;
import android.view.WindowInsets;
import android.webkit.JavascriptInterface;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;

import com.shelf.pwa.download.DownloadBridge;
import com.shelf.pwa.download.DownloadStore;
import com.shelf.pwa.offline.LocalApiServer;
import com.shelf.pwa.player.NativePlayer;

import org.json.JSONObject;

import java.net.HttpURLConnection;
import java.net.URL;

/**
 * 全屏 WebView 壳：直接加载 shelf WebUI（其本身已具备移动端响应式布局），
 * 界面与功能 100% 等同于网页端。
 *
 * 弱化「套壳浏览器」观感：
 *   - 窗口底色与页内启动屏同色，冷启动无闪烁；
 *   - 状态栏 / 导航栏透明 + edge-to-edge，由网页内容透出；
 *   - 用真实 WindowInsets 取栏高并注入 --sat/--sb 变量（WebView 里 env() 返回 0），内容避开系统栏；
 *   - 系统栏图标随网页深浅主题自适应（JS 桥接 + MutationObserver）；
 *   - 关闭 over-scroll 光晕、自定义加载失败页（不暴露系统 WebView 错误页）。
 */
public class MainActivity extends Activity {
    private static final String PREFS = "shelf_prefs";
    private static final String KEY_URL = "server_url";
    private static final String TAG = "ShelfOffline";

    private WebView webView;
    private NativePlayer nativePlayer;
    private String serverUrl;
    /** 真实状态栏/导航栏高度（CSS px=dp），由 WindowInsets 驱动，兜底取系统资源。 */
    private int lastTopDp = 0;
    private int lastBottomDp = 0;
    private boolean pageLoaded = false;
    /** 网页最近一次上报的主题（true=深色）；启动屏期间系统栏图标先用深色。 */
    private boolean lastDark = true;
    private boolean splashFinished = false;
    /** 当前是否加载 127.0.0.1 的内置 WebUI；用于避免资源缺失时递归重载。 */
    private boolean localWebMode = false;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);
        String url = getIntent().getStringExtra("url");
        if (url == null) url = sp.getString(KEY_URL, null);
        if (url == null) {
            startSetup();
            return;
        }
        serverUrl = url;

        // 透明状态栏 + 导航栏，内容顶到屏幕边缘
        getWindow().setStatusBarColor(Color.TRANSPARENT);
        getWindow().setNavigationBarColor(Color.TRANSPARENT);
        int flags = getWindow().getDecorView().getSystemUiVisibility();
        flags |= View.SYSTEM_UI_FLAG_LAYOUT_FULLSCREEN
                | View.SYSTEM_UI_FLAG_LAYOUT_STABLE
                | View.SYSTEM_UI_FLAG_LAYOUT_HIDE_NAVIGATION;
        getWindow().getDecorView().setSystemUiVisibility(flags);
        // 启动屏是暖白底色，先用深色系统栏图标；ready() 后交给网页主题
        applyThemeIcons(false);

        webView = new WebView(this);
        webView.setBackgroundColor(Color.TRANSPARENT);
        webView.setOverScrollMode(View.OVER_SCROLL_NEVER); // 去掉浏览器式边缘光晕
        WebSettings ws = webView.getSettings();
        ws.setJavaScriptEnabled(true);
        ws.setDomStorageEnabled(true);            // 网页端用 localStorage 存进度/偏好
        ws.setDatabaseEnabled(true);
        ws.setCacheMode(WebSettings.LOAD_DEFAULT);
        ws.setMediaPlaybackRequiresUserGesture(false); // 允许页面内播放器自动/编程播放
        ws.setLoadWithOverviewMode(true);
        ws.setUseWideViewPort(true);
        ws.setAllowFileAccess(false);

        // 用真实 WindowInsets 取状态栏/导航栏高度（不再依赖 WebView 里返回 0 的 env()），注入 --sat/--sb
        webView.setOnApplyWindowInsetsListener((v, insets) -> {
            float density = getResources().getDisplayMetrics().density;
            lastTopDp = Math.round(insets.getSystemWindowInsetTop() / density);
            lastBottomDp = Math.round(insets.getSystemWindowInsetBottom() / density);
            applySafeAreaToPage();
            return insets;
        });

        webView.addJavascriptInterface(new AppBridge(), "ShelfApp");
        // 离线下载：Web 端只传清单/轮询状态，实际下载在 DownloadService。
        webView.addJavascriptInterface(new DownloadBridge(this, payload ->
                runOnUiThread(() -> {
                    if (nativePlayer != null) nativePlayer.play(payload);
                })), "ShelfDownload");

        // 原生播放：WebView 只做 UI，音频交给 Media3 前台服务，状态栏/锁屏由系统托管。
        nativePlayer = new NativePlayer(this, state -> runOnUiThread(() -> {
            if (webView != null) {
                webView.evaluateJavascript(
                        "window.__shelfPlayer && window.__shelfPlayer.onState("
                                + JSONObject.quote(state) + ")", null);
            }
        }));
        webView.addJavascriptInterface(new PlayerBridge(), "ShelfPlayer");

        webView.setWebViewClient(new WebViewClient() {
            @Override
            public boolean shouldOverrideUrlLoading(WebView view, String u) {
                view.loadUrl(u);
                return true;
            }

            @Override
            public void onPageFinished(WebView view, String url) {
                super.onPageFinished(view, url);
                pageLoaded = true;
                injectThemeAndSplash();
                injectOfflineShortcut();
                applySafeAreaToPage();
                view.requestApplyInsets();
            }

            @Override
            public void onReceivedError(WebView view, WebResourceRequest request, WebResourceError error) {
                // 仅主框架失败才进入离线流程；有下载时加载本地 WebUI，否则显示错误页。
                if (request.isForMainFrame()) {
                    showOfflineOrError();
                }
            }
        });

        // 长按弹出“更改服务器”
        webView.setOnLongClickListener(v -> {
            new AlertDialog.Builder(this)
                    .setTitle("设置")
                    .setMessage("长按可随时更改服务器地址")
                    .setPositiveButton("更改服务器", (d, w) -> changeServer())
                    .setNegativeButton("取消", null)
                    .show();
            return true;
        });

        setContentView(webView);
        requestNotificationPermission();
        loadInitialPage();
    }

    /**
     * 有已下载书籍时先探测服务器：断网/服务器不可达直接进离线书架，
     * 避免 WebView 命中缓存后停在登录页，让用户以为只能登录不能离线。
     */
    private void loadInitialPage() {
        if (!hasDownloads()) {
            Log.i(TAG, "startup online mode: no downloaded books");
            webView.loadUrl(serverUrl);
            return;
        }
        new Thread(() -> {
            boolean online = probeServer();
            Log.i(TAG, "startup offline gate: downloads=yes online=" + online);
            runOnUiThread(() -> {
                if (online) {
                    localWebMode = false;
                    webView.loadUrl(serverUrl);
                } else {
                    showOfflineWeb();
                }
            });
        }, "shelf-startup-probe").start();
    }

    private boolean hasDownloads() {
        try {
            return DownloadStore.get(this).hasDoneBooks();
        } catch (Exception ignored) {
            return false;
        }
    }

    private boolean probeServer() {
        HttpURLConnection connection = null;
        try {
            URL health = new URL(new URL(serverUrl), "/api/v1/health");
            connection = (HttpURLConnection) health.openConnection();
            connection.setConnectTimeout(2500);
            connection.setReadTimeout(2500);
            connection.setRequestMethod("GET");
            int code = connection.getResponseCode();
            return code >= 200 && code < 400;
        } catch (Exception ignored) {
            return false;
        } finally {
            if (connection != null) connection.disconnect();
        }
    }

    /**
     * 注入：① 把真实状态栏/导航栏高度以 --sat / --sb 变量（及 html 内边距兜底）注入网页；
     * ② 监听启动屏移除时机，之后系统栏图标与 theme-color 跟随应用主题。
     * 注：顶栏是 sticky top-0，需 WebUI 侧把内容用 padding-top: var(--sat) 下推才能真正避开状态栏
     * （父级 html 内边距无法挪动 sticky 吸顶位置），该 WebUI 改动留作下一步。
     */
    private void injectThemeAndSplash() {
        String js = "(function(){"
                + "var d=document.documentElement;"
                + "function isDark(){return d.classList.contains('dark');}"
                + "function finish(){if(window.__shelfFinished)return;window.__shelfFinished=true;"
                + "  var m=document.querySelector('meta[name=theme-color]');"
                + "  if(m){m.setAttribute('content',isDark()?'#0b0d10':'#fafafa');}"
                + "  if(window.ShelfApp){window.ShelfApp.onSplashFinished(isDark());}}"
                + "function sync(){if(window.__shelfFinished&&window.ShelfApp){window.ShelfApp.onThemeChanged(isDark());}}"
                + "var sp=document.querySelector('shelf-launch-splash');"
                + "if(sp&&sp.parentNode){"
                + "  var mo=new MutationObserver(function(_m,obs){"
                + "    if(!document.contains(sp)){obs.disconnect();finish();}});"
                + "  mo.observe(sp.parentNode,{childList:true});"
                + "}else{finish();}"
                + "if(!window.__shelfThemeObs){"
                + "  window.__shelfThemeObs=new MutationObserver(sync);"
                + "  window.__shelfThemeObs.observe(d,{attributes:true,attributeFilter:['class']});}"
                + "})();";
        webView.evaluateJavascript(js, null);
    }

    /**
     * 登录页在断网时可能来自 WebView 缓存，不会触发 onReceivedError。
     * 有下载内容时注入一个原生入口，用户无需重启 App 也能进离线书架。
     */
    private void injectOfflineShortcut() {
        if (!hasDownloads()) return;
        String js = "(function(){"
                + "var tries=0;"
                + "function add(){"
                + "if(document.getElementById('shelf-offline-shortcut'))return;"
                + "var heading=document.querySelector('h1');"
                + "if(!heading || heading.textContent.indexOf('登录')<0){"
                + "if(tries++<20)setTimeout(add,250);return;}"
                + "var b=document.createElement('button');"
                + "b.id='shelf-offline-shortcut';b.type='button';b.textContent='离线书架';"
                + "b.style.cssText='position:fixed;right:16px;bottom:calc(16px + env(safe-area-inset-bottom));"
                + "z-index:99999;padding:10px 16px;border:1px solid #e4ded2;border-radius:999px;"
                + "background:#fffdf8;color:#111110;font-size:13px;box-shadow:0 4px 16px rgba(0,0,0,.10)';"
                + "b.addEventListener('click',function(){ShelfApp.openOffline();});"
                + "document.body.appendChild(b);"
                + "}"
                + "add();"
                + "})();";
        webView.evaluateJavascript(js, null);
    }

    /** 把真实栏高注入为 --sat/--sb 变量（WebUI 顶栏/底栏据此下推内容，避免双份偏移，不再改 html padding）。 */
    private void applySafeAreaToPage() {
        if (!pageLoaded) return;
        int top = lastTopDp > 0 ? lastTopDp : systemBarDp("status_bar_height");
        if (top <= 0) top = 24; // 兜底：约一个标准状态栏高度
        int bottom = lastBottomDp > 0 ? lastBottomDp : systemBarDp("navigation_bar_height");
        if (bottom < 0) bottom = 0;
        String js = "(function(d){"
                + "d.style.setProperty('--sat','" + top + "px');"
                + "d.style.setProperty('--sb','" + bottom + "px');"
                + "})(document.documentElement);";
        webView.evaluateJavascript(js, null);
    }

    private void showOfflineOrError() {
        if (localWebMode) {
            showErrorPage();
        } else if (hasDownloads()) {
            showOfflineWeb();
        } else {
            showErrorPage();
        }
    }

    /** 断网时启动本机 API 服务，并加载 APK 内置 WebUI。 */
    private void showOfflineWeb() {
        if (!hasDownloads()) {
            showErrorPage();
            return;
        }
        try {
            LocalApiServer local = LocalApiServer.ensure(this);
            localWebMode = true;
            Log.i(TAG, "local offline api on 127.0.0.1:" + local.getPort());
            webView.loadUrl("http://127.0.0.1:" + local.getPort() + "/index.html");
        } catch (Exception error) {
            Log.e(TAG, "failed to start local offline api", error);
            showErrorPage();
        }
    }

    /** 加载失败页：不暴露系统 WebView 的默认 “Webpage not available”。 */
    private void showErrorPage() {
        localWebMode = false;
        String html = "<html><head><meta name='viewport' "
                + "content='width=device-width,initial-scale=1,viewport-fit=cover'><style>"
                + "html,body{margin:0;height:100%;background:#f1ede4;color:#111110;"
                + "font-family:-apple-system,'Helvetica Neue',Helvetica,Arial,sans-serif;}"
                + "body{display:flex;flex-direction:column;align-items:center;"
                + "justify-content:center;gap:16px;padding:calc(28px + env(safe-area-inset-top)) "
                + "28px calc(28px + env(safe-area-inset-bottom));text-align:center;}"
                + "h1{margin:0;font-size:20px;font-weight:600;}"
                + "p{margin:0;max-width:330px;font-size:14px;line-height:1.65;"
                + "color:rgba(17,17,16,.62);}"
                + "button{margin-top:8px;padding:12px 28px;border:0;border-radius:999px;"
                + "background:#f05a32;color:#fff;font-size:14px;font-weight:600;}"
                + "</style></head><body>"
                + "<h1>无法连接到 shelf</h1>"
                + "<p>请确认手机与服务器在同一网络，且地址填写正确。</p>"
                + "<div id='offline' style='width:100%;max-width:360px;text-align:left'></div>"
                + "<button type='button' onclick='ShelfApp.retry()'>重试</button>"
                + "<script>"
                + "(function(){"
                + "var host=document.getElementById('offline');"
                + "if(!window.ShelfDownload){host.textContent='当前客户端不支持离线书架';return;}"
                + "var data={};try{data=JSON.parse(ShelfDownload.snapshot());}catch(e){}"
                + "var books=Object.keys(data).map(function(k){return data[k];})"
                + ".filter(function(b){return b.status==='done' && b.done>0;});"
                + "if(!books.length){host.innerHTML='<p style=\"font-size:12px\">还没有下载完成的书籍。</p>';return;}"
                + "var title=document.createElement('h2');"
                + "title.textContent='已下载书籍';"
                + "title.style.cssText='font-size:14px;margin:4px 0 8px';"
                + "host.appendChild(title);"
                + "books.forEach(function(book){"
                + "var row=document.createElement('div');"
                + "row.style.cssText='display:flex;align-items:center;gap:10px;padding:10px 0;border-top:1px solid rgba(17,17,16,.10)';"
                + "var name=document.createElement('div');"
                + "name.textContent=book.title || ('书籍 '+book.bookId);"
                + "name.style.cssText='flex:1;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap';"
                + "var btn=document.createElement('button');"
                + "btn.type='button';btn.textContent='播放';"
                + "btn.style.cssText='padding:8px 18px;border-radius:999px;background:#f05a32;color:#fff;border:0;font-size:13px';"
                + "btn.addEventListener('click',function(){ShelfDownload.playBook(book.bookId);});"
                + "row.appendChild(name);row.appendChild(btn);host.appendChild(row);"
                + "});"
                + "})();"
                + "</script>"
                + "</body></html>";
        webView.loadDataWithBaseURL(serverUrl, html, "text/html", "utf-8", null);
    }

    private void reload() {
        localWebMode = false;
        if (webView != null && serverUrl != null) {
            webView.loadUrl(serverUrl);
        }
    }

    /**
     * dark=true → 深色应用背景，系统栏图标用浅色；
     * dark=false → 浅色背景，图标用深色。
     */
    private void applyThemeIcons(boolean dark) {
        int flags = getWindow().getDecorView().getSystemUiVisibility();
        if (dark) {
            flags &= ~View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            flags &= ~View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        } else {
            flags |= View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR;
            flags |= View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR;
        }
        getWindow().getDecorView().setSystemUiVisibility(flags);
    }

    /** 取系统栏高度并换算成 CSS px（dp），取不到时返回 0。 */
    private int systemBarDp(String resourceName) {
        int id = getResources().getIdentifier(resourceName, "dimen", "android");
        if (id <= 0) return 0;
        float density = getResources().getDisplayMetrics().density;
        return density > 0 ? Math.round(getResources().getDimensionPixelSize(id) / density) : 0;
    }

    /** Android 13+ 通知权限；没有它前台播放服务的媒体通知不会显示。 */
    private void requestNotificationPermission() {
        if (Build.VERSION.SDK_INT >= 33
                && checkSelfPermission(Manifest.permission.POST_NOTIFICATIONS)
                != PackageManager.PERMISSION_GRANTED) {
            requestPermissions(new String[]{Manifest.permission.POST_NOTIFICATIONS}, 1001);
        }
    }

    /** 网页 → 原生播放控制的桥；所有调用切回主线程执行。 */
    private class PlayerBridge {
        @JavascriptInterface
        public void play(String json) {
            runOnUiThread(() -> {
                if (nativePlayer != null) nativePlayer.play(json);
            });
        }

        @JavascriptInterface
        public void setAuth(String token) {
            runOnUiThread(() -> {
                if (nativePlayer != null) nativePlayer.setAuth(token);
            });
        }

        @JavascriptInterface
        public void pause() {
            runOnUiThread(() -> {
                if (nativePlayer != null) nativePlayer.pause();
            });
        }

        @JavascriptInterface
        public void resume() {
            runOnUiThread(() -> {
                if (nativePlayer != null) nativePlayer.resume();
            });
        }

        @JavascriptInterface
        public void seekTo(double absoluteSec) {
            runOnUiThread(() -> {
                if (nativePlayer != null) nativePlayer.seekTo(absoluteSec);
            });
        }

        @JavascriptInterface
        public void seekToTrack(int index, double positionInTrackSec) {
            runOnUiThread(() -> {
                if (nativePlayer != null) nativePlayer.seekToTrack(index, positionInTrackSec);
            });
        }

        @JavascriptInterface
        public void setRate(float rate) {
            runOnUiThread(() -> {
                if (nativePlayer != null) nativePlayer.setRate(rate);
            });
        }

        @JavascriptInterface
        public void setVolume(float volume) {
            runOnUiThread(() -> {
                if (nativePlayer != null) nativePlayer.setVolume(volume);
            });
        }

        @JavascriptInterface
        public void next() {
            runOnUiThread(() -> {
                if (nativePlayer != null) nativePlayer.next();
            });
        }

        @JavascriptInterface
        public void previous() {
            runOnUiThread(() -> {
                if (nativePlayer != null) nativePlayer.previous();
            });
        }

        @JavascriptInterface
        public void setSleepTimer(String json) {
            runOnUiThread(() -> {
                if (nativePlayer != null) nativePlayer.setSleepTimer(json);
            });
        }

        @JavascriptInterface
        public void clearSleepTimer() {
            runOnUiThread(() -> {
                if (nativePlayer != null) nativePlayer.clearSleepTimer();
            });
        }

        @JavascriptInterface
        public void stop() {
            runOnUiThread(() -> {
                if (nativePlayer != null) nativePlayer.stop();
            });
        }
    }

    private class AppBridge {
        /** 启动屏已退场：此后系统栏配色跟随应用主题。 */
        @JavascriptInterface
        public void onSplashFinished(boolean dark) {
            splashFinished = true;
            lastDark = dark;
            runOnUiThread(() -> applyThemeIcons(dark));
        }

        /** 网页主题切换。启动屏期间忽略（此时底色是启动屏的暖白）。 */
        @JavascriptInterface
        public void onThemeChanged(boolean dark) {
            lastDark = dark;
            if (splashFinished) {
                runOnUiThread(() -> applyThemeIcons(dark));
            }
        }

        /** 加载失败页上的「重试」。 */
        @JavascriptInterface
        public void retry() {
            runOnUiThread(() -> reload());
        }

        /** 登录页的「离线书架」入口。 */
        @JavascriptInterface
        public void openOffline() {
            runOnUiThread(MainActivity.this::showOfflineWeb);
        }
    }

    /** 清除已保存的地址并回到录入页。 */
    private void changeServer() {
        getSharedPreferences(PREFS, MODE_PRIVATE).edit().remove(KEY_URL).apply();
        startSetup();
    }

    private void startSetup() {
        Intent i = new Intent(this, SetupActivity.class);
        startActivity(i);
        finish();
    }

    @Override
    public void onBackPressed() {
        // 禁用 WebView 内部历史返回：右滑边缘手势 / 返回键不再在网页内「后退」，
        // 直接交还系统默认行为（退出 Activity），避免误触。
        super.onBackPressed();
    }

    @Override
    protected void onDestroy() {
        LocalApiServer.stopIfRunning();
        if (nativePlayer != null) {
            nativePlayer.release();
            nativePlayer = null;
        }
        if (webView != null) {
            webView.destroy();
            webView = null;
        }
        super.onDestroy();
    }
}
