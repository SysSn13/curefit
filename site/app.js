// Lazy-load player and ensure single playback

document.addEventListener('click', function (e) {
  const btn = e.target.closest('.play-btn');
  if (!btn) return;

  const url = btn.dataset.url;
  const type = btn.dataset.type;
  const media = document.createElement(type === 'audio' ? 'audio' : 'video');
  media.controls = true;
  media.src = url;
  media.style.width = '100%';

  btn.parentNode.replaceChild(media, btn);

  // Pause any others that are already playing
  pauseOthers(media);
  media.play();
}, false);

function pauseOthers(current) {
  document.querySelectorAll('audio,video').forEach(function (m) {
    if (m !== current) m.pause();
  });
}

document.addEventListener('play', function (e) {
  pauseOthers(e.target);
}, true); 