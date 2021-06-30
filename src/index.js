const fs = require("fs");
const { ipcRenderer } = require("electron");
let openedFilePath;
const codearea = document.getElementById("codearea");
const runBtn = document.getElementById("runBtn");
const saveNotice = document.getElementById("saveNotice")
const closeSaveNotice = document.getElementById("closeSaveNotice")
const dragFile = document.getElementById('drag-file')
const filePathDisplay = document.getElementById('filePathDisplay')
// 下面一句是要引入yu组件库
// import 'yu.css.ui/dist/index.css'
// customTitlebar
const customTitlebar = require('custom-electron-titlebar');

//拖动文件到框中，显示绝对路径
let path

dragFile.addEventListener('drop', function(e) {
    e.preventDefault()
    e.stopPropagation()

    for(let f of e.dataTransfer.files){
        // console.log('the files you dragged: ', f)
        path = f.path
    }

    ipcRenderer.send('ondragstart', path)
})

dragFile.addEventListener('dragover', function (e) {
    e.preventDefault()
    e.stopPropagation()
})

ipcRenderer.on('getFilePath', (event, data) => {
  // let txtarea = document.getElementById('txtarea')
  // txtarea.innerHTML = data
  filePathDisplay.value = data
  console.log(data)
})


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
//     args: [codearea.value]
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

runBtn.addEventListener('mouseup', async () => {
  console.log(openedFilePath)
  sendToPython(openedFilePath);
});
  
// runBtn.dispatchEvent(new Event('mouseup'));

ipcRenderer.on("fileOpened", (event, { contents, filePath }) => {
    openedFilePath = filePath;
    document.getElementById('codearea').value = contents;
})

function removeActive(){
  saveNotice.classList.remove("active")
}

closeSaveNotice.addEventListener('click', () => {
  removeActive()
})

ipcRenderer.on("saveFile" , (event) => {
    const currentCodeValue = codearea.value;
    fs.writeFileSync(openedFilePath, currentCodeValue, "utf-8")
    saveNotice.classList.add("active")
    setTimeout("removeActive()", 1500);
})
