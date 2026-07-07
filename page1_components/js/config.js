
export const USE_LOCAL_API = true; // trueならFlask版。

// falseなら、USE_LOCAL_API = false → Flaskを完全に飛ばして、フロントから直接Supabaseに繋ぐ
//falseの方は、**「まだFlaskの認証システムを作る前、一番最初の実験段階」**で使っていたものです。
// あの頃はまだservice_role_keyも無く、
// Flaskで守る仕組みも無かったので、フロントが直接Supabaseのanon_keyを使って通信していました。


// Supabase(クラウド版)
export const SUPABASE_URL = 'https://tekrwutayfleorpfbuhc.supabase.co';
export const SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InRla3J3dXRheWZsZW9ycGZidWhjIiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODI1NzA1ODIsImV4cCI6MjA5ODE0NjU4Mn0.eG8ENxN1BxZn_yFdxrsytz2Qa9LCT95WgdRqLkEDs80';


 //ローカルFlask版
//export const LOCAL_API_URL = 'http://127.0.0.1:5000';


// 変更後(Renderで発行された本物のURLに置き換え)
export const LOCAL_API_URL = 'https://store-iphone.onrender.com';