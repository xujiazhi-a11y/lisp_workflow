const fs = require("fs");
const { ipcRenderer } = require("electron");
let openedFilePath;
const textarea = document.getElementById("textarea");
const btn = document.getElementById("btn");
const saveNotice = document.getElementById("saveNotice")
const closeSaveNotice = document.getElementById("closeSaveNotice")
// 下面一句是要引入yu组件库
// import 'yu.css.ui/dist/index.css'
// customTitlebar
const customTitlebar = require('custom-electron-titlebar');


new customTitlebar.Titlebar({
    //menuPosition: 'left',
    // order: (title, menu),
  titleHorizontalAlignment: 'left',
	backgroundColor: customTitlebar.Color.fromHex('#162834'),
  icon: 'E:/electron_Dev/textEditor/logo/zhiyu.svg'
    // icon: "E:/electron_Dev/pythonElectron/icon/志语.svg",
});

// 下面是python-shell的写法，之前找打包方法的时候，发现spawn有一个讲挺好，暂时先不用python-shell了吧（不知道以后是不是要再用回来）
// const {PythonShell} = require('python-shell');

// let options = {
//     mode: 'text',
//     pythonPath: 'C:\\Users\\ThinkPad\\AppData\\Local\\Programs\\Python\\Python38\\python.exe',
//     pythonOptions: ['-u'], // get print results in real-time
//     scriptPath: 'py',
//     args: [textarea.value]
// };

// function sendToPythonShell() {
//   PythonShell.run('Catkins_Dream.py', options, function (err, results) {
//       if (err) throw err;
//       // results is an array consisting of messages collected during execution
//       console.log('results: %j', results);
//   });
// }

function sendToPython(filePath) {
    let python = require('child_process').spawn('python', ['./venv/py/Catkins_Dream.py', filePath]);
    python.stdout.on('data', function (data) {
      console.log("Python response: ", data.toString('utf8'));
    //   result.textContent = data.toString('utf8');
    });
  
    python.stderr.on('data', (data) => {
      console.error(`stderr: ${data}`);
    });
  
    python.on('close', (code) => {
      if(`${code}` == 0){
        console.log(`子进程正常退出`)
      }
      else if (`${code}` == 1) {
        console.log(`子进程异常退出，退出编码： ${code}`);
      }
    });
  
  }

btn.addEventListener('mouseup', async () => {
  console.log(openedFilePath)
  sendToPython(openedFilePath);
});
  
// btn.dispatchEvent(new Event('mouseup'));

ipcRenderer.on("fileOpened", (event, { contents, filePath }) => {
    openedFilePath = filePath;
    document.getElementById('textarea').value = contents;
})

function removeActive(){
  saveNotice.classList.remove("active")
}

closeSaveNotice.addEventListener('click', () => {
  removeActive()
})

ipcRenderer.on("saveFile" , (event) => {
    const currentCodeValue = textarea.value;
    fs.writeFileSync(openedFilePath, currentCodeValue, "utf-8")
    saveNotice.classList.add("active")
    setTimeout("removeActive()", 1500);
})
