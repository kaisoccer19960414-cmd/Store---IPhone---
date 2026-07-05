import { saveToDB, readFromDB, toggleQuizList } from './quizUI.js';
import { initSwipeNavigation } from './swipeNav.js';

document.addEventListener('DOMContentLoaded', () => {
  initSwipeNavigation();

  document.getElementById('save-btn').addEventListener('click', saveToDB);
  document.getElementById('read-btn').addEventListener('click', readFromDB);
  document.getElementById('fetch-all-btn').addEventListener('click', toggleQuizList);
});