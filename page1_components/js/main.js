import { saveToDB, readFromDB, renderAllQuizzes,toggleQuizList } from './quizUI.js';
import { initSwipeNavigation } from './swipeNav.js';

document.addEventListener('DOMContentLoaded', () => {
  initSwipeNavigation();
//自動で表示オフ    renderAllQuizzes();

  document.getElementById('save-btn')?.addEventListener('click', saveToDB);
  document.getElementById('read-btn')?.addEventListener('click', readFromDB);
   document.getElementById('fetch-all-btn')?.addEventListener('click', toggleQuizList);

});