const { app, BrowserWindow, ipcMain } = require('electron');
const path = require('path');

let win;

function createWindow() {
    win = new BrowserWindow({
        width: 200,                     // 与 pet.html 中的 WIN_W 一致
        height: 200,                    // 与 WIN_H 一致
        x: 800,
        y: 400,
        transparent: true,
        frame: false,
        alwaysOnTop: true,
        hasShadow: false,
        resizable: false,
        backgroundColor: '#00000000',   // 关键：强制透明
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'),
            contextIsolation: true,
            nodeIntegration: false,
        }
    });

    win.loadFile('pet.html');
}

// 接收渲染进程的窗口移动请求
ipcMain.on('move-window', (event, { x, y }) => {
    if (win) win.setPosition(x, y);
});

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
    // 不退出，保持后台
});