/*
 * inject.js
 * =========
 * 対象アプリの通常ページに1行(<script src="/__calltracer__/inject.js">)
 * 追加するだけで、そのページのfetch()をCallTracerのタイムラインに
 * リアルタイムで報告できるようにするスクリプト。
 *
 * 設計方針:
 * - localStorageの "calltracer_session_id" を見て、値がある時だけ
 *   報告を行う(この値は、管理者がViewer画面でセッションを開始した時に
 *   セットされる。同一オリジンなのでタブ間で共有される)。
 * - このスクリプト自体は認証を一切行わない。認証は既に
 *   /session/start の時点(is_adminチェック)で完了しており、
 *   ここではその結果である session_id を運ぶだけ。
 * - fetch呼び出し自体をブロックしないよう、報告はfire-and-forgetで行う。
 */
(function () {
  const SESSION_KEY = "calltracer_session_id";
  const originalFetch = window.fetch;

  // このスクリプト自身が読み込まれたURLから、CallTracerバックエンドの
  // オリジン(スキーム+ホスト)を特定する(フロント/バックエンドが
  // 別ドメインの場合に、相対パスが誤って「今開いているページのドメイン」
  // へ向いてしまうのを防ぐため)。
  const _scriptEl = document.currentScript;
  const BASE_URL = _scriptEl ? new URL(_scriptEl.src).origin : "";

  // --- クロスオリジン対応: URLの ?calltracer_session=... を拾う ---
  // localStorageはオリジン(ドメイン)ごとに別々に管理されるため、
  // Viewer(バックエンドのドメイン)が保存したsession_idは、
  // このスクリプトが動いている対象アプリのドメイン(フロントエンド)
  // からはそのままでは見えない。
  // そのため、Viewer側で「対象アプリをこのセッションID付きで開く」
  // リンクを踏んでもらい、そのURLパラメータを読み取って、この
  // ドメイン自身のlocalStorageに保存し直す(以後はこのURL無しでも使える)。
  (function bootstrapSessionFromUrl() {
    try {
      const params = new URLSearchParams(window.location.search);
      const fromUrl = params.get("calltracer_session");
      if (fromUrl) {
        localStorage.setItem(SESSION_KEY, fromUrl);
        // URLに残したままだと共有・再読み込み時に紛らわしいので消しておく
        params.delete("calltracer_session");
        const cleanedSearch = params.toString();
        const newUrl =
          window.location.pathname +
          (cleanedSearch ? "?" + cleanedSearch : "") +
          window.location.hash;
        window.history.replaceState(null, "", newUrl);
      }
    } catch (e) {
      /* URL操作に失敗しても致命的ではないので無視する */
    }
  })();

  function reportUrl() {
    return BASE_URL + "/__calltracer__/events";
  }

  function report(event) {
    const sessionId = localStorage.getItem(SESSION_KEY);
    if (!sessionId) {
      return;
    }
    // 自分自身の報告(POST /__calltracer__/events)まで再度フックしてしまわないよう、
    // 必ずoriginalFetchを使う。
    originalFetch(reportUrl(), {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CallTracer-Session": sessionId,
      },
      body: JSON.stringify(event),
    }).catch(function () {
      /* Viewerが閉じている等で失敗しても、対象アプリの動作に影響させない */
    });
  }

  window.fetch = function (...args) {
    const sessionId = localStorage.getItem(SESSION_KEY);
    if (!sessionId) {
      // セッションが無ければ、素通しするだけ(オーバーヘッドもほぼ無い)
      return originalFetch.apply(this, args);
    }

    const [resource, config] = args;
    const url =
      typeof resource === "string"
        ? resource
        : resource && resource.url
        ? resource.url
        : String(resource);
    const method =
      (config && config.method) || (resource && resource.method) || "GET";
    const callId = "js_" + Date.now() + "_" + Math.random().toString(36).slice(2);

    // 重要: このリクエスト自体にも X-CallTracer-Session ヘッダーを付ける。
    // これが無いと、バックエンド側(before_request)がこのリクエストを
    // 「管理者が見ているセッション」と認識できず、Python側のトレースが
    // 一切有効化されない(/__calltracer__/events への報告だけでは、
    // JS側の記録しか残らない)。
    const mergedConfig = Object.assign({}, config || {});
    if (mergedConfig.headers instanceof Headers) {
      const newHeaders = new Headers(mergedConfig.headers);
      newHeaders.set("X-CallTracer-Session", sessionId);
      mergedConfig.headers = newHeaders;
    } else {
      mergedConfig.headers = Object.assign(
        {},
        mergedConfig.headers || {},
        { "X-CallTracer-Session": sessionId }
      );
    }

    report({
      id: callId,
      timestamp: Date.now() / 1000,
      source: "javascript",
      type: "fetch_start",
      depth: 0,
      payload: { url: url, method: method, call_id: callId },
    });

    const promise = originalFetch.call(this, resource, mergedConfig);

    promise.then(
      function (response) {
        report({
          id: callId + "_end",
          timestamp: Date.now() / 1000,
          source: "javascript",
          type: "fetch_end",
          depth: 0,
          payload: { url: url, status: response.status, call_id: callId },
        });
      },
      function () {
        report({
          id: callId + "_end",
          timestamp: Date.now() / 1000,
          source: "javascript",
          type: "fetch_end",
          depth: 0,
          payload: { url: url, status: null, call_id: callId, error: true },
        });
      }
    );

    return promise;
  };
})();