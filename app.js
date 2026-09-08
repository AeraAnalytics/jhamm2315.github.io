const today = document.querySelector('#today');
const now = new Date();
today.textContent = now.toLocaleDateString('en-US', { weekday: 'short', month: 'short', day: 'numeric' });

const dialog = document.querySelector('#directive-dialog');
const toast = document.querySelector('.toast');
document.querySelector('#new-directive').addEventListener('click', () => dialog.showModal());
dialog.addEventListener('close', () => {
  if (dialog.returnValue === 'confirm') {
    toast.classList.add('show');
    window.setTimeout(() => toast.classList.remove('show'), 3000);
  }
});

const sidebar = document.querySelector('.sidebar');
document.querySelector('.menu-button').addEventListener('click', () => sidebar.classList.toggle('open'));
document.querySelectorAll('.nav-item').forEach((item) => item.addEventListener('click', () => {
  document.querySelectorAll('.nav-item').forEach((link) => link.classList.remove('active'));
  item.classList.add('active');
  sidebar.classList.remove('open');
}));

const search = document.querySelector('#search');
document.addEventListener('keydown', (event) => {
  if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === 'k') {
    event.preventDefault();
    search.focus();
  }
  if (event.key === 'Escape') search.blur();
});

search.addEventListener('input', () => {
  const query = search.value.toLowerCase().trim();
  document.querySelectorAll('.decision-row, .project-row').forEach((row) => {
    row.style.display = !query || row.textContent.toLowerCase().includes(query) ? '' : 'none';
  });
});

document.querySelector('#sync-time').textContent = now.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit' });
