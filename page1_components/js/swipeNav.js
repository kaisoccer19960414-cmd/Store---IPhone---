export function initSwipeNavigation(targetUrl = './chat.html') {
  let touchStartX = 0;
  let touchStartY = 0;

  window.addEventListener('touchstart', (e) => {
    touchStartX = e.touches[0].clientX;
    touchStartY = e.touches[0].clientY;
  }, { passive: true });

  window.addEventListener('touchend', (e) => {
    const diffX = e.changedTouches[0].clientX - touchStartX;
    const diffY = Math.abs(e.changedTouches[0].clientY - touchStartY);

    if (touchStartX < 50 && diffX > 100 && diffY < 50) {
      window.location.href = targetUrl;
    }
  }, { passive: true });
}