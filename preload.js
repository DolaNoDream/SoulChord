const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
    moveWindow: (x, y) => ipcRenderer.send('move-window', { x, y }),
    moveWindowBy: (dx, dy) => ipcRenderer.send('move-window-by', { dx, dy })
});