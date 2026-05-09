(function () {
  'use strict';

  // ===== Configuration =====
  const CONFIG = {
    API_BASE: '',
    COUNTDOWN_SECONDS: 6,
    LOADING_MESSAGES: [
      { title: 'Initializing engine...', subtitle: 'Preparing secure environment', step: 1 },
      { title: 'Fetching video streams...', subtitle: 'Scanning available formats', step: 2 },
      { title: 'Downloading media...', subtitle: 'Processing video streams', step: 3 },
      { title: 'Finalizing package...', subtitle: 'Encrypting data transfer', step: 3 },
      { title: 'Download starting...', subtitle: 'Connection established', step: 4 },
    ],
    POLL_INTERVAL: 1000,
    NOTIF_DURATION: 5000,
  };

  // ===== State =====
  const state = {
    taskId: null,
    countdownTimer: null,
    pollingTimer: null,
    isDownloading: false,
    countdownStart: 0,
  };

  // ===== DOM References =====
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => [...ctx.querySelectorAll(sel)];

  const dom = {};

  function cacheDom() {
    dom.heroSection = $('#heroSection');
    dom.downloadCard = $('#downloadCard');
    dom.inputWrapper = $('#inputWrapper');
    dom.videoUrl = $('#videoUrl');
    dom.inputClear = $('#inputClear');
    dom.urlHint = $('#urlHint');
    dom.downloadBtn = $('#downloadBtn');
    dom.btnText = $('.btn-text', dom.downloadBtn);
    dom.helpBtn = $('#helpBtn');
    dom.helpOverlay = $('#helpOverlay');
    dom.helpClose = $('#helpClose');
    dom.contactNav = $('#contactNav');
    dom.contactOverlay = $('#contactOverlay');
    dom.contactClose = $('#contactClose');

    dom.loadingOverlay = $('#loadingOverlay');
    dom.loadingTitle = $('#loadingTitle');
    dom.loadingSubtitle = $('#loadingSubtitle');
    dom.progressFill = $('#progressFill');
    dom.loadingTime = $('#loadingTime');
    dom.loadingPercent = $('#loadingPercent');
    dom.loadingSteps = $('#loadingSteps');

    dom.notification = $('#notification');
    dom.notifIcon = $('#notifIcon');
    dom.notifTitle = $('#notifTitle');
    dom.notifMessage = $('#notifMessage');
    dom.notifClose = $('#notifClose');
  }

  // ===== URL Validation =====
  function isValidSkoolUrl(url) {
    if (!url || typeof url !== 'string') return false;
    url = url.trim();
    try {
      const u = new URL(url);
      return /^(.+\.)?skool\.com$/i.test(u.hostname);
    } catch {
      return false;
    }
  }

  // ===== Notification System =====
  let notifTimeout = null;

  function showNotification(type, title, message) {
    clearTimeout(notifTimeout);
    dom.notification.className = 'notification ' + type;
    dom.notifTitle.textContent = title;
    dom.notifMessage.textContent = message;

    dom.notifIcon.innerHTML = type === 'success'
      ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>'
      : type === 'warning'
        ? '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>'
        : '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="10"/><line x1="15" y1="9" x2="9" y2="15"/><line x1="9" y1="9" x2="15" y2="15"/></svg>';

    requestAnimationFrame(() => dom.notification.classList.add('show'));

    if (type === 'success') {
      notifTimeout = setTimeout(() => {
        dom.notification.classList.remove('show');
      }, CONFIG.NOTIF_DURATION);
    }
  }

  // ===== Input Handling =====
  function updateButtonState() {
    const url = dom.videoUrl.value.trim();
    const valid = isValidSkoolUrl(url);
    dom.downloadBtn.disabled = !valid || state.isDownloading;
  }

  // ===== Help Modal =====
  function openHelp() {
    dom.helpOverlay.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closeHelp() {
    dom.helpOverlay.classList.remove('active');
    document.body.style.overflow = '';
  }

  // ===== Bind Events =====
  function bindEvents() {
    dom.notifClose.addEventListener('click', function () {
      dom.notification.classList.remove('show');
      clearTimeout(notifTimeout);
    });

    dom.videoUrl.addEventListener('input', function () {
      const val = this.value.trim();
      dom.inputClear.classList.toggle('visible', val.length > 0);
      updateButtonState();

      if (val.length > 5) {
        if (isValidSkoolUrl(val)) {
          dom.downloadCard.className = 'download-card is-valid';
          dom.urlHint.className = 'url-hint success';
          dom.urlHint.textContent = 'Valid Skool URL detected';
        } else {
          dom.downloadCard.className = 'download-card';
          dom.urlHint.className = 'url-hint';
          dom.urlHint.textContent = 'Paste a Skool.com video URL to get started';
        }
      } else {
        dom.downloadCard.className = 'download-card';
        dom.urlHint.className = 'url-hint';
        dom.urlHint.textContent = 'Paste a Skool.com video URL to get started';
      }
    });

    dom.inputClear.addEventListener('click', function () {
      dom.videoUrl.value = '';
      dom.videoUrl.focus();
      dom.inputClear.classList.remove('visible');
      dom.downloadCard.className = 'download-card';
      dom.urlHint.className = 'url-hint';
      dom.urlHint.textContent = 'Paste a Skool.com video URL to get started';
      updateButtonState();
    });

    dom.downloadBtn.addEventListener('click', handleDownload);

    dom.videoUrl.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' && !dom.downloadBtn.disabled) {
        handleDownload();
      }
    });

    dom.helpBtn.addEventListener('click', openHelp);
    dom.helpClose.addEventListener('click', closeHelp);
    dom.helpOverlay.addEventListener('click', function (e) {
      if (e.target === dom.helpOverlay) closeHelp();
    });

    dom.contactNav.addEventListener('click', function (e) {
      e.preventDefault();
      dom.contactOverlay.classList.add('active');
      document.body.style.overflow = 'hidden';
    });
    dom.contactClose.addEventListener('click', function () {
      dom.contactOverlay.classList.remove('active');
      document.body.style.overflow = '';
    });
    dom.contactOverlay.addEventListener('click', function (e) {
      if (e.target === dom.contactOverlay) {
        dom.contactOverlay.classList.remove('active');
        document.body.style.overflow = '';
      }
    });

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        if (dom.helpOverlay.classList.contains('active')) closeHelp();
        if (dom.contactOverlay.classList.contains('active')) {
          dom.contactOverlay.classList.remove('active');
          document.body.style.overflow = '';
        }
      }
    });
  }

  // ===== Loading Screen =====
  function showLoadingScreen() {
    dom.loadingOverlay.classList.add('active');
    dom.loadingTitle.textContent = CONFIG.LOADING_MESSAGES[0].title;
    dom.loadingSubtitle.textContent = CONFIG.LOADING_MESSAGES[0].subtitle;
    dom.progressFill.style.width = '0%';
    dom.loadingPercent.textContent = '0%';
    dom.loadingTime.textContent = 'Estimated time: 6s';
    resetSteps();
    activateStep(1);
    document.body.style.overflow = 'hidden';
  }

  function hideLoadingScreen() {
    dom.loadingOverlay.classList.remove('active');
    document.body.style.overflow = '';
  }

  function resetSteps() {
    $$('.step', dom.loadingSteps).forEach(s => {
      s.classList.remove('active', 'done');
    });
  }

  function activateStep(num) {
    $$('.step', dom.loadingSteps).forEach(s => {
      const step = parseInt(s.dataset.step, 10);
      s.classList.remove('active', 'done');
      if (step === num) s.classList.add('active');
      else if (step < num) s.classList.add('done');
    });
  }

  function setLoadingMessage(index) {
    const msg = CONFIG.LOADING_MESSAGES[Math.min(index, CONFIG.LOADING_MESSAGES.length - 1)];

    dom.loadingTitle.classList.add('changing');
    dom.loadingSubtitle.classList.add('changing');

    setTimeout(() => {
      dom.loadingTitle.textContent = msg.title;
      dom.loadingSubtitle.textContent = msg.subtitle;
      dom.loadingTitle.classList.remove('changing');
      dom.loadingSubtitle.classList.remove('changing');
    }, 300);

    activateStep(msg.step);
  }

  function updateProgress(percent) {
    dom.progressFill.style.width = Math.min(percent, 100) + '%';
    dom.loadingPercent.textContent = Math.min(percent, 100) + '%';

    if (percent >= 100) {
      dom.loadingTime.textContent = 'Complete!';
    }
  }

  // ===== Countdown Logic =====
  function startCountdown() {
    state.countdownStart = Date.now();
    const totalMs = CONFIG.COUNTDOWN_SECONDS * 1000;
    let lastMsgIndex = -1;

    return new Promise((resolve) => {
      function tick() {
        const elapsed = Date.now() - state.countdownStart;
        const progress = Math.min(elapsed / totalMs, 1);
        const remaining = Math.max(0, CONFIG.COUNTDOWN_SECONDS - elapsed / 1000);

        updateProgress(Math.round(progress * 60));

        dom.loadingTime.textContent = 'Estimated time: ' + Math.ceil(remaining) + 's';

        const msgIndex = Math.min(
          Math.floor(progress * CONFIG.LOADING_MESSAGES.length),
          CONFIG.LOADING_MESSAGES.length - 1
        );

        if (msgIndex !== lastMsgIndex && msgIndex < CONFIG.LOADING_MESSAGES.length) {
          setLoadingMessage(msgIndex);
          lastMsgIndex = msgIndex;
        }

        if (progress >= 1) {
          setLoadingMessage(CONFIG.LOADING_MESSAGES.length - 1);
          updateProgress(60);
          resolve();
        } else {
          requestAnimationFrame(tick);
        }
      }

      tick();
    });
  }

  // ===== Download Flow =====
  async function handleDownload() {
    const url = dom.videoUrl.value.trim();

    if (!isValidSkoolUrl(url)) {
      dom.downloadCard.className = 'download-card has-error';
      dom.urlHint.className = 'url-hint error';
      dom.urlHint.textContent = 'Please enter a valid Skool.com URL';
      dom.videoUrl.focus();
      return;
    }

    state.isDownloading = true;
    updateButtonState();

    showLoadingScreen();

    await startCountdown();

    try {
      const res = await fetch(CONFIG.API_BASE + '/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url: url }),
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.error || 'Failed to start download');
      }

      const data = await res.json();
      state.taskId = data.task_id;

      await pollForCompletion(data.task_id);

    } catch (err) {
      hideLoadingScreen();
      state.isDownloading = false;
      updateButtonState();

      dom.downloadCard.className = 'download-card has-error';
      dom.urlHint.className = 'url-hint error';

      if (err.message.includes('Authentication') || err.message.includes('403')) {
        dom.urlHint.textContent = 'Authentication required. The server session may have expired.';
        showNotification('warning', 'Authentication Required', 'The server session may have expired. Contact the admin.');
      } else if (err.message.includes('No video') || err.message.includes('not found')) {
        dom.urlHint.textContent = 'No video found on this page. Make sure the URL is correct.';
        showNotification('error', 'No Video Found', err.message);
      } else {
        dom.urlHint.textContent = err.message.substring(0, 120);
        showNotification('error', 'Download Failed', err.message);
      }
    }
  }

  async function pollForCompletion(taskId) {
    return new Promise((resolve, reject) => {
      function poll() {
        fetch(CONFIG.API_BASE + '/api/download/' + taskId + '/status')
          .then(function (res) {
            if (!res.ok) throw new Error('Status check failed');
            return res.json();
          })
          .then(function (data) {
            if (data.status === 'completed') {
              updateProgress(100);
              dom.loadingTitle.textContent = 'Download complete!';
              dom.loadingSubtitle.textContent = 'Preparing your file...';
              activateStep(4);
              dom.loadingSteps.querySelector('.step[data-step="4"]').classList.add('done');

              setTimeout(function () {
                triggerFileDownload(taskId);
                hideLoadingScreen();
                state.isDownloading = false;
                updateButtonState();
                showNotification('success', 'Download Complete', 'Your video has been downloaded successfully.');
                resolve();
              }, 800);

              return;
            }

            if (data.status === 'error') {
              hideLoadingScreen();
              state.isDownloading = false;
              updateButtonState();
              reject(new Error(data.error || 'Download failed'));
              return;
            }

            var realProgress = Math.min(data.progress || 0, 100);
            var displayProgress = Math.min(60 + (realProgress * 0.4), 99);
            updateProgress(Math.round(displayProgress));

            dom.loadingTitle.textContent = 'Downloading... ' + realProgress + '%';
            dom.loadingSubtitle.textContent = 'Processing video streams';
            dom.loadingTime.textContent = 'Downloading video';

            state.pollingTimer = setTimeout(poll, CONFIG.POLL_INTERVAL);
          })
          .catch(function (err) {
            reject(err);
          });
      }

      state.pollingTimer = setTimeout(poll, 500);
    });
  }

  function triggerFileDownload(taskId) {
    var a = document.createElement('a');
    a.href = CONFIG.API_BASE + '/api/download/' + taskId + '/file';
    a.download = '';
    a.style.display = 'none';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
  }

  // ===== Entrance Animations =====
  function initAnimations() {
    const els = $$('.hero-badge, .hero-title, .download-card, .features, .hero-footer');
    els.forEach(function (el, i) {
      el.style.animationDelay = (0.1 + i * 0.1) + 's';
    });
  }

  // ===== Init =====
  function init() {
    cacheDom();
    bindEvents();
    updateButtonState();
    initAnimations();

    if (!dom.videoUrl.value.trim()) {
      dom.videoUrl.focus();
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
