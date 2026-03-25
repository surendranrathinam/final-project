// ─── WoodCraft ERP — main.js ──────────────────────────────────────────────

// Modal helpers
function closeModal(id) {
  document.getElementById(id).classList.remove('open');
}

// Close modal on overlay click
document.addEventListener('click', function(e) {
  if (e.target.classList.contains('modal-overlay')) {
    e.target.classList.remove('open');
  }
});

// Close modal on Escape key
document.addEventListener('keydown', function(e) {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(m => m.classList.remove('open'));
  }
});

// Auto-dismiss flash messages after 4 seconds
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.flash').forEach(function(flash) {
    setTimeout(function() {
      flash.style.transition = 'opacity .4s';
      flash.style.opacity = '0';
      setTimeout(() => flash.remove(), 400);
    }, 4000);
  });
});

// Tab switching
function showTab(id, btn) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
  document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  btn.classList.add('active');
}
