package com.shelf.pwa;

import android.app.Activity;
import android.content.Intent;
import android.content.SharedPreferences;
import android.net.Uri;
import android.os.Bundle;
import android.text.TextUtils;
import android.view.Gravity;
import android.widget.Button;
import android.widget.EditText;
import android.widget.LinearLayout;
import android.widget.TextView;
import android.widget.Toast;

import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;

/**
 * 首次启动让用户输入 shelf 服务器地址（如 http://192.168.31.103:8090），
 * 保存前先请求 /api/v1/health 验证确实是 shelf 服务端；不是则提示且不进入。
 */
public class SetupActivity extends Activity {
    private static final String PREFS = "shelf_prefs";
    private static final String KEY_URL = "server_url";

    private EditText input;
    private Button go;

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        SharedPreferences sp = getSharedPreferences(PREFS, MODE_PRIVATE);
        String url = sp.getString(KEY_URL, null);
        if (!TextUtils.isEmpty(url)) {
            startMain(url);
            return;
        }

        LinearLayout root = new LinearLayout(this);
        root.setOrientation(LinearLayout.VERTICAL);
        root.setGravity(Gravity.CENTER);
        root.setPadding(48, 48, 48, 48);
        // 与启动屏 / 窗口底色一致的暖白纸感，避免冷启动闪黑
        root.setBackgroundColor(0xFFF1EDE4);

        TextView title = new TextView(this);
        title.setText("shelf");
        title.setTextSize(30);
        title.setTextColor(0xFF111110);
        title.setGravity(Gravity.CENTER);
        title.setPadding(0, 0, 0, 8);

        TextView sub = new TextView(this);
        sub.setText("有声书库 · 移动端");
        sub.setTextColor(0x8F111110);
        sub.setTextSize(14);
        sub.setGravity(Gravity.CENTER);
        sub.setPadding(0, 0, 0, 32);

        TextView hint = new TextView(this);
        hint.setText("输入 shelf 服务器地址");
        hint.setTextColor(0x8F111110);
        hint.setPadding(0, 0, 0, 12);

        input = new EditText(this);
        input.setHint("http://192.168.31.103:8090");
        input.setTextColor(0xFF111110);
        input.setSingleLine(true);

        go = new Button(this);
        go.setText("进入");
        go.setBackgroundColor(0xFFF05A32);
        go.setTextColor(0xFFFFFFFF);
        go.setPadding(0, 24, 0, 24);
        go.setOnClickListener(v -> verifyAndEnter());

        root.addView(title);
        root.addView(sub);
        root.addView(hint);
        root.addView(input);
        root.addView(go);
        setContentView(root);
    }

    /** 校验地址格式并请求 /api/v1/health，确认是 shelf 服务端才进入。 */
    private void verifyAndEnter() {
        String raw = input.getText().toString().trim();
        if (TextUtils.isEmpty(raw)) {
            toast("请输入地址");
            return;
        }
        if (!raw.startsWith("http://") && !raw.startsWith("https://")) {
            raw = "http://" + raw;
        }
        Uri uri = Uri.parse(raw);
        if (TextUtils.isEmpty(uri.getHost())) {
            toast("地址格式不正确，请检查");
            return;
        }
        final String url = raw.replaceAll("/+$", "");

        go.setEnabled(false);
        go.setText("验证中…");

        new Thread(() -> {
            String error = null;
            try {
                HttpURLConnection conn =
                        (HttpURLConnection) new URL(url + "/api/v1/health").openConnection();
                conn.setConnectTimeout(5000);
                conn.setReadTimeout(5000);
                conn.setRequestProperty("Accept", "application/json");
                int code = conn.getResponseCode();
                if (code != 200) {
                    error = "HTTP " + code;
                } else {
                    JSONObject json = new JSONObject(readAll(conn.getInputStream()));
                    // shelf 健康检查固定返回 { status, version, db, ... }
                    if (TextUtils.isEmpty(json.optString("status"))
                            && !json.has("version")) {
                        error = "响应不是 shelf 服务";
                    }
                }
                conn.disconnect();
            } catch (Exception e) {
                error = "无法连接";
            }
            final String err = error;
            final String okUrl = url;
            runOnUiThread(() -> {
                go.setEnabled(true);
                go.setText("进入");
                if (err == null) {
                    getSharedPreferences(PREFS, MODE_PRIVATE)
                            .edit().putString(KEY_URL, okUrl).apply();
                    startMain(okUrl);
                } else {
                    toast("不是有效的 shelf 服务地址（" + err + "），请检查后重试");
                }
            });
        }, "shelf-verify").start();
    }

    private String readAll(InputStream in) throws Exception {
        StringBuilder sb = new StringBuilder();
        try (BufferedReader r = new BufferedReader(
                new InputStreamReader(in, StandardCharsets.UTF_8))) {
            String line;
            while ((line = r.readLine()) != null) {
                sb.append(line);
            }
        }
        return sb.toString();
    }

    private void toast(String msg) {
        Toast.makeText(this, msg, Toast.LENGTH_LONG).show();
    }

    private void startMain(String url) {
        Intent i = new Intent(this, MainActivity.class);
        i.putExtra("url", url);
        startActivity(i);
        finish();
    }
}
