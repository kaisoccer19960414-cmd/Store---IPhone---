import { saveToDB, readFromDB, renderAllQuizzes } from './quizUI.js';
import { initSwipeNavigation } from './swipeNav.js';

document.addEventListener('DOMContentLoaded', () => {
  initSwipeNavigation();
  renderAllQuizzes();

  document.getElementById('save-btn')?.addEventListener('click', saveToDB);
  document.getElementById('read-btn')?.addEventListener('click', readFromDB);
});