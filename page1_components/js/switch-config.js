// 使い方: node switch-config.js local  または  node switch-config.js prod
const fs = require('fs');
const path = require('path');

const target = process.argv[2]; // 'local' か 'prod'

if (target !== 'local' && target !== 'prod') {
  console.error('使い方: node switch-config.js local  または  node switch-config.js prod');
  process.exit(1);
}

const sourceFile = path.join(__dirname, `config.${target}.js`);
const destFile = path.join(__dirname, 'config.js');

fs.copyFileSync(sourceFile, destFile);
console.log(`✅ config.js を「${target}」用の設定に切り替えました`);