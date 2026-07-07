import { saveToDB, readFromDB, toggleQuizList, initAuthorSelect, loadMoreQuizzes } from './quizUI.js';
import { initSwipeNavigation } from './swipeNav.js';

document.addEventListener('DOMContentLoaded', () => {
  initSwipeNavigation();
  initAuthorSelect();

  document.getElementById('save-btn').addEventListener('click', saveToDB);
  document.getElementById('read-btn').addEventListener('click', readFromDB);
  document.getElementById('fetch-all-btn').addEventListener('click', toggleQuizList);
  document.getElementById('load-more-btn')?.addEventListener('click', loadMoreQuizzes);
});