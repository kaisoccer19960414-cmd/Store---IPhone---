import { saveToDB, readFromDB, toggleQuizList, initAuthorSelect } from './quizUI.js';
import { initSwipeNavigation } from './swipeNav.js';

document.addEventListener('DOMContentLoaded', () => {
  initSwipeNavigation();
  initAuthorSelect(); // 投稿者ドロップダウンの中身を準備しておく

  document.getElementById('save-btn').addEventListener('click', saveToDB);
  document.getElementById('read-btn').addEventListener('click', readFromDB);
  document.getElementById('fetch-all-btn').addEventListener('click', toggleQuizList);
});