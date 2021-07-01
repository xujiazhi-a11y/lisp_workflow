import { app, BrowserWindow, Menu} from 'electron';
import path from 'path';
const {dialog} = require('electron');
const fs = require("fs")
// require("electron-reload")(__dirname);
const ipcMain = require('electron').ipcMain

// Keep a global reference of the window object, if you don't, the window will
// be closed automatically when the JavaScript object is garbage collected.
let mainWindow;

let template = [
  {
    label: "文件",
    submenu : [
      {
        id: 'save-file',
        // enabled: false,
        accelerator: "Ctrl + S",
        label: "保存",
        click: async () => {
          mainWindow.webContents.send("saveFile")
        },
      },
      {
        label: "打开",
        accelerator: "Ctrl + O",
        click: async () => {
          const { filePaths } = await dialog.showOpenDialog({
            properties: ["openFile"],
          });
          //获取文件绝对路径
          const file = filePaths[0];
          //获取文件内容
          const contents = fs.readFileSync(file, "utf-8");
          mainWindow.webContents.send('fileOpened', {
            contents, filePath: file});
          // 只有打开文件之后，保存文件才可以点
          const saveFileItem = menu.getMenuItemById('save-file')
          saveFileItem.enabled = true;
        },
      }
    ]  
  },
];

const menu = Menu.buildFromTemplate(template);
Menu.setApplicationMenu(menu);

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (require('electron-squirrel-startup')) { // eslint-disable-line global-require
  app.quit();
}

const createWindow = () => {
  // Create the browser window.
  mainWindow = new BrowserWindow({
    width: 1000,
    height: 800,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
      enableRemoteModule: true,
    },
    frame: false, //隐藏自带的titleBar，使用customTitleBar
    backgroundColor: '#162834',
    icon: 'logo/zhiyu.ico'
  });

  // and load the index.html of the app.
  mainWindow.loadURL(`file://${__dirname}/index.html`);

  // Open the DevTools.
  mainWindow.webContents.openDevTools();

  // Emitted when the window is closed.
  mainWindow.on('closed', () => {
    // Dereference the window object, usually you would store windows
    // in an array if your app supports multi windows, this is the time
    // when you should delete the corresponding element.
    mainWindow = null;
  });
};

ipcMain.on('ondragstart', (event, filePath) => {
  console.log(filePath)
  readFile(filePath)
  //event.sender.send('fileData', filePath)
  //这里的readFile在尝试把filePath传给textArea，而不是文件内容
  function readFile(filePath) {
    event.sender.send('getFilePath', filePath)
  }
})

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.on('ready', createWindow);

// Quit when all windows are closed.
app.on('window-all-closed', () => {
  // On OS X it is common for applications and their menu bar
  // to stay active until the user quits explicitly with Cmd + Q
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  // On OS X it's common to re-create a window in the app when the
  // dock icon is clicked and there are no other windows open.
  if (mainWindow === null) {
    createWindow();
  }
});

// In this file you can include the rest of your app's specific main process
// code. You can also put them in separate files and import them here.
