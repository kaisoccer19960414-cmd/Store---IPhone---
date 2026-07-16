// ブラウザ標準の alert/confirm/prompt は、利用者の設定でブロックされることがあるため、
// 自作のポップアップ(モーダル)に置き換える。

let stylesInjected = false;

function injectStylesOnce() {
  if (stylesInjected) return;
  stylesInjected = true;

  const style = document.createElement('style');
  style.textContent = `
    .app-modal-overlay {
      position: fixed;
      inset: 0;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      padding: 20px;
      box-sizing: border-box;
    }
    .app-modal-box {
      background: #ffffff;
      border-radius: 12px;
      padding: 24px;
      width: 100%;
      max-width: 340px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
      font-family: inherit;
    }
    .app-modal-message {
      margin: 0 0 16px;
      font-size: 1rem;
      line-height: 1.5;
      white-space: pre-wrap;
      color: #222;
    }
    .app-modal-input {
      width: 100%;
      padding: 10px;
      font-size: 1rem;
      box-sizing: border-box;
      margin-bottom: 16px;
      border: 1px solid #ccc;
      border-radius: 6px;
    }
    .app-modal-buttons {
      display: flex;
      justify-content: flex-end;
      gap: 8px;
    }
    .app-modal-buttons button {
      padding: 9px 18px;
      border-radius: 6px;
      border: none;
      font-size: 0.95rem;
      cursor: pointer;
    }
    .app-modal-cancel {
      background: #eee;
      color: #333;
    }
    .app-modal-ok {
      background: #8B4513;
      color: white;
    }
    .app-modal-loading-box {
      display: flex;
      flex-direction: column;
      align-items: center;
      text-align: center;
    }
    .app-spinner {
      width: 32px;
      height: 32px;
      border: 4px solid #eee;
      border-top-color: #8B4513;
      border-radius: 50%;
      margin-bottom: 12px;
      animation: app-spin 0.8s linear infinite;
    }
    @keyframes app-spin {
      to { transform: rotate(360deg); }
    }
  `;
  document.head.appendChild(style);
}

function createOverlay({ message, showInput = false, showCancel = true, inputType = 'text', defaultValue = '' }) {
  injectStylesOnce();

  const overlay = document.createElement('div');
  overlay.className = 'app-modal-overlay';

  const box = document.createElement('div');
  box.className = 'app-modal-box';

  const messageEl = document.createElement('p');
  messageEl.className = 'app-modal-message';
  messageEl.textContent = message;
  box.appendChild(messageEl);

  let input = null;
  if (showInput) {
    input = document.createElement('input');
    input.className = 'app-modal-input';
    input.type = inputType;
    input.value = defaultValue;
    box.appendChild(input);
  }

  const buttonRow = document.createElement('div');
  buttonRow.className = 'app-modal-buttons';

  let cancelBtn = null;
  if (showCancel) {
    cancelBtn = document.createElement('button');
    cancelBtn.className = 'app-modal-cancel';
    cancelBtn.textContent = 'キャンセル';
    buttonRow.appendChild(cancelBtn);
  }

  const okBtn = document.createElement('button');
  okBtn.className = 'app-modal-ok';
  okBtn.textContent = 'OK';
  buttonRow.appendChild(okBtn);

  box.appendChild(buttonRow);
  overlay.appendChild(box);
  document.body.appendChild(overlay);

  if (input) {
    setTimeout(() => input.focus(), 0);
  }

  return { overlay, input, cancelBtn, okBtn };
}

// 通信中の表示(Renderのスリープ復帰待ちなど、時間がかかる処理向け)
let loadingOverlay = null;

export function showLoading(message = '通信中...') {
  hideLoading(); // 念のため、表示済みのものがあれば消してから出す
  injectStylesOnce();

  const overlay = document.createElement('div');
  overlay.className = 'app-modal-overlay';

  const box = document.createElement('div');
  box.className = 'app-modal-box app-modal-loading-box';

  const spinner = document.createElement('div');
  spinner.className = 'app-spinner';

  const messageEl = document.createElement('p');
  messageEl.className = 'app-modal-message';
  messageEl.style.margin = '0';
  messageEl.textContent = message;

  box.appendChild(spinner);
  box.appendChild(messageEl);
  overlay.appendChild(box);
  document.body.appendChild(overlay);

  loadingOverlay = overlay;
}

export function hideLoading() {
  if (loadingOverlay) {
    loadingOverlay.remove();
    loadingOverlay = null;
  }
}
export function showAlert(message) {
  return new Promise((resolve) => {
    const { overlay, okBtn } = createOverlay({ message, showCancel: false });
    okBtn.addEventListener('click', () => {
      overlay.remove();
      resolve();
    });
  });
}

// confirmの代わり(true/falseを返す)
export function showConfirm(message) {
  return new Promise((resolve) => {
    const { overlay, cancelBtn, okBtn } = createOverlay({ message });
    cancelBtn.addEventListener('click', () => {
      overlay.remove();
      resolve(false);
    });
    okBtn.addEventListener('click', () => {
      overlay.remove();
      resolve(true);
    });
  });
}

// promptの代わり(入力した文字列、またはキャンセル時はnullを返す)
export function showPrompt(message, defaultValue = '', inputType = 'text') {
  return new Promise((resolve) => {
    const { overlay, input, cancelBtn, okBtn } = createOverlay({
      message,
      showInput: true,
      defaultValue,
      inputType
    });

    cancelBtn.addEventListener('click', () => {
      overlay.remove();
      resolve(null);
    });
    okBtn.addEventListener('click', () => {
      const value = input.value;
      overlay.remove();
      resolve(value);
    });

    // Enterキーでも送信できるようにする
    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') okBtn.click();
    });
  });
}


// 自動で閉じる軽い通知(保存成功など、読んだらすぐ消えて困らないメッセージ向け)
export function showToast(message, duration = 500) {
  injectStylesOnce();

  const overlay = document.createElement('div');
  overlay.className = 'app-modal-overlay';

  const box = document.createElement('div');
  box.className = 'app-modal-box';

  const messageEl = document.createElement('p');
  messageEl.className = 'app-modal-message';
  messageEl.style.margin = '0'; // ボタンがない分、余白を詰める
  messageEl.textContent = message;
  box.appendChild(messageEl);

  overlay.appendChild(box);
  document.body.appendChild(overlay);

  setTimeout(() => {
    overlay.remove();
  }, duration);
}