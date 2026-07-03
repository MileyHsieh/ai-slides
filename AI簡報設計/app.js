/* ==========================================
   AI簡報設計 - 互動與同步邏輯 (app.js)
   ========================================== */

(function() {
  // ==================== 全域狀態與配置 ====================
  const CONFIG = {
    ntfyServer: 'https://ntfy.sh',
    // 視覺色表 (與 CSS 的視覺系統一致)
    colors: ['#1A1A1A', '#555555', '#E65C00', '#D35400', '#2B6CB0', '#4A5568']
  };

  const state = {
    roomId: '',
    currentSlide: 1,
    totalSlides: 28,
    wordCounts: {},       // { '單字': 次數 }
    processedMsgIds: new Set(), // 避免輪詢時重複處理相同單字
    eventSource: null,
    pollingInterval: null,
    // 糾錯遊戲狀態
    errorsFound: new Set(),
    totalErrors: 4,
    errorsInfo: {
      title: {
        title: "❌ 標題過於冗長且符號浮誇",
        desc: "標題「感恩大自然投影片簡報!!!」包含贅字與多個驚嘆號，製造雜訊。應該直接精簡為核心概念：<span class='hl-blue'>「大自然的恩惠」</span>。"
      },
      text: {
        title: "❌ 密密麻麻的文字牆 (複製貼上)",
        desc: "聽眾無法在3秒內閱讀整段文字。應遵循<span class='hl-blue'>「圖 ＞ 詞 ＞ 文」</span>與<span class='hl-blue'>「3重點原則」</span>，把空氣、水、食物提煉為核心詞彙，刪除廢話。"
      },
      image: {
        title: "❌ 歪斜且畫質低劣的浮水印配圖",
        desc: "歪斜的排版和低畫質帶浮水印的插圖會降低專業度。應使用<span class='emphasis'>高品質、無浮水印且具視覺延伸感</span>的真實照片。"
      },
      style: {
        title: "❌ 刺眼的配色與混亂的字體",
        desc: "螢光綠背景配紅字新細明體與彩虹閃爍字，嚴重干擾閱讀（雜訊極大）。應改為<span class='hl-blue'>軟白/淺色背景</span>、<span class='font-bold'>粗黑大字</span>，重點用藍色螢光筆劃線。"
      }
    }
  };

  // ==================== 初始化 ====================
  function init() {
    // 自動根據當前網址 Hostname 產生唯一的房間代碼，避免與他人衝突
    // 若為本地開啟 (file://)，Hostname 為空，則預設 temple-local
    const cleanHostname = window.location.hostname.replace(/[^a-zA-Z0-9]/g, '') || 'local';
    state.roomId = `temple-room-${cleanHostname}`;
    console.log(`自動建立通訊頻道：${state.roomId}`);

    // 初始化簡報顯示
    showSlide(state.currentSlide);
    resizeSlides();
    setupEvents();

    // 建立學生端二維碼與連結 (連結即為本簡報網址本身，學生點開後即可看簡報、可在第二頁直接回答問題)
    setupQRAndUrls();

    // 開始監聽文字雲的單字傳送
    startListeningWords();

    // 初始化 Canvas 尺寸
    initWordCloudCanvas();
  }

  // 設定二維碼與網址
  function setupQRAndUrls() {
    const currentUrl = window.location.href;
    
    // 顯示文字 URL
    const urlDisplay = document.getElementById('presenter-url');
    if (urlDisplay) {
      // 顯示簡化版的網址以利手動輸入，但 QR 碼會包含完整 URL
      urlDisplay.textContent = window.location.origin + window.location.pathname;
    }

    // 動態生成 QR 碼指向當前網頁
    const qrImg = document.getElementById('presenter-qr');
    if (qrImg) {
      qrImg.src = `https://api.qrserver.com/v1/create-qr-code/?size=300x300&data=${encodeURIComponent(currentUrl)}`;
    }
  }

  // ==================== 換頁與事件綁定 ====================
  function setupEvents() {
    // 鍵盤換頁事件
    window.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {
        nextSlide();
      } else if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
        prevSlide();
      }
    });

    // 換頁控制按鈕
    document.getElementById('prev-slide-btn').addEventListener('click', prevSlide);
    document.getElementById('next-slide-btn').addEventListener('click', nextSlide);
    
    // 全螢幕按鈕
    document.getElementById('fullscreen-btn').addEventListener('click', toggleFullscreen);

    // 清空單字按鈕
    document.getElementById('clear-words-btn').addEventListener('click', () => {
      state.wordCounts = {};
      document.getElementById('response-count').textContent = '0';
      drawWordCloud();
      document.getElementById('word-cloud-placeholder').style.display = 'block';
    });

    // Slide 2: 學生回答送出按鈕
    const submitBtn = document.getElementById('slide2-submit-btn');
    const answerInput = document.getElementById('slide2-answer-input');
    
    if (submitBtn && answerInput) {
      submitBtn.addEventListener('click', submitAnswer);
      answerInput.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') submitAnswer();
      });
    }

    // Slide 7: 糾錯小遊戲
    const clickableElements = document.querySelectorAll('.clickable-element');
    clickableElements.forEach(el => {
      el.addEventListener('click', function() {
        const errorKey = this.getAttribute('data-error');
        handleGameClick(errorKey, this);
      });
    });

    // 糾錯一鍵淨化按鈕
    document.getElementById('purify-btn').addEventListener('click', purifyNGSlide);

    // 視窗自適應（手機旋轉、視窗縮放時重新計算縮放比例）
    window.addEventListener('resize', () => {
      resizeSlides();
      initWordCloudCanvas();
      drawWordCloud();
    });
  }

  // ==================== 響應式縮放：等比縮放簡報畫布以適配任何螢幕 ====================
  function resizeSlides() {
    const container = document.getElementById('slides-container');
    if (!container) return;
    const designWidth = 1280;
    const designHeight = 720;
    const scale = Math.min(window.innerWidth / designWidth, window.innerHeight / designHeight);
    const offsetX = (window.innerWidth - designWidth * scale) / 2;
    const offsetY = (window.innerHeight - designHeight * scale) / 2;
    container.style.transform = `scale(${scale})`;
    container.style.marginLeft = `${offsetX}px`;
    container.style.marginTop = `${offsetY}px`;
  }

  function showSlide(index) {
    if (index < 1 || index > state.totalSlides) return;
    
    // 隱藏當前幻燈片
    const activeSlide = document.querySelector('.active-slide');
    if (activeSlide) {
      activeSlide.classList.remove('active-slide');
    }

    // 顯示目標幻燈片
    const nextSlideEl = document.getElementById(`slide-${index}`);
    if (nextSlideEl) {
      nextSlideEl.classList.add('active-slide');
    }

    state.currentSlide = index;
    document.getElementById('slide-number-display').textContent = `${state.currentSlide} / ${state.totalSlides}`;

    // 如果切換到文字雲頁面，重新繪製以防 Canvas 尺寸問題
    if (index === 2) {
      setTimeout(() => {
        initWordCloudCanvas();
        drawWordCloud();
      }, 50);
    }
  }

  function nextSlide() {
    if (state.currentSlide < state.totalSlides) {
      showSlide(state.currentSlide + 1);
    }
  }

  function prevSlide() {
    if (state.currentSlide > 1) {
      showSlide(state.currentSlide - 1);
    }
  }

  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(err => {
        console.error(`無法啟用全螢幕: ${err.message}`);
      });
    } else {
      document.exitFullscreen();
    }
  }

  // ==================== Slide 2: 學生回答提交 (POST) ====================
  function submitAnswer() {
    const input = document.getElementById('slide2-answer-input');
    const errorEl = document.getElementById('slide2-form-error');
    const successEl = document.getElementById('slide2-success-msg');
    const word = input.value.trim();

    if (!word) {
      showMsg(errorEl, '⚠️ 請輸入單字！', true);
      return;
    }
    if (word.length > 8) {
      showMsg(errorEl, '⚠️ 請縮短在 8 個字以內！', true);
      return;
    }

    // 清理狀態
    errorEl.style.display = 'none';
    successEl.style.display = 'none';

    // 鎖定 UI 防止重複傳送
    const submitBtn = document.getElementById('slide2-submit-btn');
    submitBtn.setAttribute('disabled', 'true');
    input.setAttribute('disabled', 'true');
    submitBtn.textContent = '傳送中';

    // 送出至 ntfy.sh 頻道
    const publishUrl = `${CONFIG.ntfyServer}/${state.roomId}`;
    
    fetch(publishUrl, {
      method: 'POST',
      body: word,
      headers: {
        'Content-Type': 'text/plain; charset=utf-8'
      }
    })
    .then(res => {
      if (res.ok) {
        showMsg(successEl, '✓ 送出成功！請看右側文字雲！', false);
        input.value = ''; // 清空
      } else {
        showMsg(errorEl, '⚠️ 伺服器連線失敗，請重試！', true);
      }
    })
    .catch(err => {
      console.error(err);
      showMsg(errorEl, '⚠️ 網路傳送失敗，請確認網路！', true);
    })
    .finally(() => {
      // 解鎖 UI
      submitBtn.removeAttribute('disabled');
      input.removeAttribute('disabled');
      submitBtn.textContent = '送出';
    });
  }

  function showMsg(element, text, isError) {
    element.textContent = text;
    element.style.display = 'block';
    
    // 如果是成功訊息，3 秒後自動隱藏
    if (!isError) {
      setTimeout(() => {
        element.style.display = 'none';
      }, 3000);
    }
  }

  // ==================== 即時接收單字：雙軌同步機制 (SSE + Polling) ====================
  function startListeningWords() {
    const isLocalFile = window.location.protocol === 'file:';
    
    if (isLocalFile) {
      console.log("偵測到本地 file:// 協議開啟，自動啟用相容型 HTTP 輪詢 (Polling)...");
      startPolling();
    } else {
      console.log("偵測到網路/伺服器開啟，優先嘗試 EventSource (SSE)...");
      try {
        const sseUrl = `${CONFIG.ntfyServer}/${state.roomId}/sse`;
        state.eventSource = new EventSource(sseUrl);

        state.eventSource.onmessage = (event) => {
          try {
            const data = JSON.parse(event.data);
            const word = data.message ? data.message.trim() : '';
            if (word && word !== 'keepalive') {
              // 記錄 ID 防止輪詢備用機制重複處理
              if (!state.processedMsgIds.has(data.id)) {
                state.processedMsgIds.add(data.id);
                handleIncomingWord(word);
              }
            }
          } catch (e) {
            console.error("解析 SSE JSON 失敗：", e);
          }
        };

        state.eventSource.onerror = (err) => {
          console.warn("EventSource SSE 出錯。為確保連線，自動啟用 Polling 輪詢備用機制...");
          state.eventSource.close();
          startPolling(); // 降級為輪詢
        };
      } catch (e) {
        console.warn("無法啟動 EventSource，自動轉為 Polling 輪詢機制...", e);
        startPolling();
      }
    }
  }

  // 啟動 3 秒輪詢
  function startPolling() {
    if (state.pollingInterval) return; // 已在輪詢中

    const pollUrl = `${CONFIG.ntfyServer}/${state.roomId}/json?poll=1`;
    
    const pollFunction = () => {
      fetch(pollUrl)
      .then(res => {
        if (!res.ok) return '';
        return res.text();
      })
      .then(text => {
        if (!text) return;
        // ntfy.sh JSON 輪詢回傳是以換行符分隔的 JSON 對象字串
        const lines = text.split('\n');
        lines.forEach(line => {
          if (!line.trim()) return;
          try {
            const data = jsonParseSafe(line);
            if (data && data.event === 'message' && data.message) {
              const word = data.message.trim();
              if (word && !state.processedMsgIds.has(data.id)) {
                state.processedMsgIds.add(data.id);
                handleIncomingWord(word);
              }
            }
          } catch(err) {
            // 忽略個別行解析錯誤
          }
        });
      })
      .catch(err => {
        console.warn("輪詢抓取失敗：", err);
      });
    };

    // 立即抓取一次，隨後每 3 秒抓取一次
    pollFunction();
    state.pollingInterval = setInterval(pollFunction, 3000);
  }

  function jsonParseSafe(str) {
    try { return JSON.parse(str); } 
    catch(e) { return null; }
  }

  function handleIncomingWord(word) {
    const cleanWord = word.substring(0, 10);
    state.wordCounts[cleanWord] = (state.wordCounts[cleanWord] || 0) + 1;
    
    // 更新累計數量
    const totalCount = Object.values(state.wordCounts).reduce((a, b) => a + b, 0);
    document.getElementById('response-count').textContent = totalCount;

    // 隱藏 Canvas 佔位提示
    const placeholder = document.getElementById('word-cloud-placeholder');
    if (placeholder) placeholder.style.display = 'none';

    // 重繪文字雲
    drawWordCloud();
  }

  // ==================== 文字雲 Canvas 繪製演算法 ====================
  let canvas, ctx;

  function initWordCloudCanvas() {
    canvas = document.getElementById('word-cloud-canvas');
    if (!canvas) return;
    ctx = canvas.getContext('2d');
    
    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * window.devicePixelRatio;
    canvas.height = rect.height * window.devicePixelRatio;
    canvas.style.width = rect.width + 'px';
    canvas.style.height = rect.height + 'px';
    ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
  }

  function intersects(box1, box2) {
    return !(box1.x + box1.w < box2.x || 
             box2.x + box2.w < box1.x || 
             box1.y + box1.h < box2.y || 
             box2.y + box2.h < box1.y);
  }

  function drawWordCloud() {
    if (!canvas || !ctx) return;
    
    const w = canvas.width / window.devicePixelRatio;
    const h = canvas.height / window.devicePixelRatio;
    
    ctx.clearRect(0, 0, w, h);

    const words = Object.keys(state.wordCounts).map(word => {
      return { text: word, count: state.wordCounts[word] };
    });

    if (words.length === 0) return;

    // 按次數大到小排序
    words.sort((a, b) => b.count - a.count);

    const maxCount = words[0].count;
    const minCount = words[words.length - 1].count;
    
    const maxFontSize = 60;
    const minFontSize = 20;
    const placedBoxes = [];

    words.forEach((item, index) => {
      let fontSize = minFontSize;
      if (maxCount !== minCount) {
        fontSize = minFontSize + ((item.count - minCount) / (maxCount - minCount)) * (maxFontSize - minFontSize);
      } else {
        fontSize = 36;
      }

      ctx.font = `900 ${fontSize}px "Noto Sans TC", sans-serif`;
      ctx.textBaseline = 'middle';
      
      const metrics = ctx.measureText(item.text);
      const textWidth = metrics.width;
      const textHeight = fontSize * 1.2;

      // 阿基米德螺旋線找尋碰撞空格
      let theta = 0;
      let placed = false;
      const centerX = w / 2;
      const centerY = h / 2;
      
      let x = centerX;
      let y = centerY;
      
      const step = 0.15;
      const distanceMultiplier = 3.0;

      for (let i = 0; i < 800; i++) {
        const r = distanceMultiplier * theta;
        x = centerX + r * Math.cos(theta) - (textWidth / 2);
        y = centerY + r * Math.sin(theta) - (textHeight / 2);

        const currentBox = {
          x: x,
          y: y,
          w: textWidth + 8,
          h: textHeight + 8
        };

        if (currentBox.x < 5 || currentBox.x + currentBox.w > w - 5 ||
            currentBox.y < 5 || currentBox.y + currentBox.h > h - 5) {
          theta += step;
          continue;
        }

        let collision = false;
        for (let j = 0; j < placedBoxes.length; j++) {
          if (intersects(currentBox, placedBoxes[j])) {
            collision = true;
            break;
          }
        }

        if (!collision) {
          placedBoxes.push(currentBox);
          
          let color = CONFIG.colors[index % CONFIG.colors.length];
          if (index === 0) color = CONFIG.colors[2]; // 最大單字為橘色
          
          ctx.fillStyle = color;
          ctx.font = `900 ${fontSize}px "Noto Sans TC", sans-serif`;
          ctx.fillText(item.text, x + 4, y + (textHeight / 2));
          placed = true;
          break;
        }

        theta += step;
      }

      // 降級放置在空隙
      if (!placed) {
        x = Math.max(10, Math.min(w - textWidth - 10, Math.random() * (w - textWidth)));
        y = Math.max(10, Math.min(h - textHeight - 10, Math.random() * (h - textHeight)));
        ctx.fillStyle = '#A0AEC0';
        ctx.font = `500 ${minFontSize}px "Noto Sans TC", sans-serif`;
        ctx.fillText(item.text, x, y + (textHeight / 2));
      }
    });
  }

  // ==================== 糾錯小遊戲 ====================
  function handleGameClick(key, element) {
    if (state.errorsFound.has(key)) return;

    state.errorsFound.add(key);
    element.classList.add('element-rectified');

    const feedbackTitle = document.getElementById('feedback-text');
    const info = state.errorsInfo[key];
    
    const infoHtml = `
      <div style="margin-bottom:0.8rem;"><strong style="font-size:1.25rem; color:#1A1A1A;">${info.title}</strong></div>
      <p style="font-size:1.1rem; line-height:1.6; color:#555555;">${info.desc}</p>
    `;
    feedbackTitle.innerHTML = infoHtml;

    const foundCountEl = document.getElementById('found-count');
    foundCountEl.textContent = state.errorsFound.size;

    if (state.errorsFound.size === state.totalErrors) {
      const purifyBtn = document.getElementById('purify-btn');
      purifyBtn.classList.remove('btn-disabled');
      purifyBtn.removeAttribute('disabled');
      
      const foundCounterBox = document.querySelector('.found-counter');
      foundCounterBox.innerHTML = "🎉 恭喜你抓出了所有錯誤！請點擊「一鍵淨化簡報」按鈕！";
      foundCounterBox.style.backgroundColor = "rgba(135, 206, 250, 0.25)";
      foundCounterBox.style.color = "#2B6CB0";
    }
  }

  function purifyNGSlide() {
    const ngSlide = document.getElementById('ng-slide');
    if (!ngSlide) return;

    ngSlide.classList.add('purified-slide-canvas');

    ngSlide.innerHTML = `
      <div class="ng-header">大自然的恩惠</div>
      <div class="ng-layout-body">
        <div class="ng-leftclickable">
          <p class="font-large" style="margin-bottom:1rem; font-weight:700;">
            大自然默默供給我們生命所需：
          </p>
          <ul class="bullet-list" style="margin-left:1.5rem; font-size:1.3rem; font-weight:900;">
            <li style="margin-bottom: 0.8rem;"><span class="hl-blue">呼吸的空氣</span>（綠色植物的奉獻）</li>
            <li style="margin-bottom: 0.8rem;"><span class="hl-blue">生命的水源</span>（清涼純淨的溪泉）</li>
            <li style="margin-bottom: 0.8rem;"><span class="hl-blue">滋養的食物</span>（大地五穀與鮮果）</li>
          </ul>
        </div>
        <div class="ng-rightclickable">
          <div class="ng-image-placeholder" style="background:#FFF9E6; width:100%; height:90%; border-radius:12px; display:flex; flex-direction:column; justify-content:center; align-items:center;">
            <span style="font-size:3rem; margin-bottom:0.5rem;">🌻</span>
            <span style="font-size:1.1rem; font-weight:900; color:#E65C00;">視覺延伸照片</span>
            <span style="font-size:0.9rem; color:#777; margin-top:0.3rem;">(高清滿版向日葵)</span>
          </div>
        </div>
      </div>
      <div class="ng-footer">
        大自然慷笥予我們一切，這是我們生命賴以生存的基石。
      </div>
    `;

    const purifyBtn = document.getElementById('purify-btn');
    purifyBtn.classList.add('btn-disabled');
    purifyBtn.setAttribute('disabled', 'true');
    purifyBtn.innerHTML = "✨ 淨化完成";

    const feedbackTitle = document.getElementById('feedback-text');
    feedbackTitle.innerHTML = `
      <div style="color:#2B6CB0; font-weight:900; font-size:1.3rem; margin-bottom:0.5rem;">✨ 簡報淨化成功！</div>
      <p style="line-height:1.6; font-size:1.1rem;">
        投影片已全面進化：符合<span class="hl-blue">白底粗黑字</span>、消除無關雜訊、每頁條列不超過3個重點，並預留了高解析度插圖位置。現在，大腦是不是清爽多了？
      </p>
    `;
  }

  // 啟動初始化
  window.addEventListener('DOMContentLoaded', init);

})();
