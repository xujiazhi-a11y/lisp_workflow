const fs = require("fs");
const { ipcRenderer } = require("electron");
let openedFilePath = __dirname + '\\初始空白.txt';
const codearea = document.getElementById("codearea");
const runBtn = document.getElementById("runBtn");
const saveNotice = document.getElementById("saveNotice")
const closeSaveNotice = document.getElementById("closeSaveNotice")
const dragFile = document.getElementById('drag-file')
const filePathDisplay = document.getElementById('filePathDisplay')
const messageDialog = document.getElementById('messageDialog')
const messageDialogContent = document.getElementById('messageDialogContent')
// 下面一句是要引入yu组件库
// import 'yu.css.ui/dist/index.css'
// customTitlebar
const customTitlebar = require('custom-electron-titlebar');
const { contextId } = require("process");

//拖动文件到框中，显示绝对路径
let path

//一开始初始化codearea内容为初始.txt的内容：
function initCodearea() {
  const initialContent = fs.readFileSync(__dirname + '\\初始说明.txt', "utf-8")
  codearea.value = initialContent
}
initCodearea()

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


// 这里是对于某个操作结束时出现的消息弹框，去除hidden，开始显示
function removeHidden() {
  messageDialog.classList.remove("hidden")
}

function addHidden() {
  messageDialog.classList.add('hidden')
}

function displayMessageBox(pythonResponse) {
  if (pythonResponse.indexOf('合好的音视频文件') !== -1) {
    messageDialogContent.innerHTML = '合并成功！'
    removeHidden()
    setTimeout('addHidden()', 1500)
  }
}

function sendToPython(filePath) {
    let python = require('child_process').spawn('python', ['./py/Catkins_Dream.py', filePath]);
    python.stdout.on('data', function (data) {
      console.log("絮梦1.0 >>>", data.toString('utf8'));
      let pythonResponse = data.toString('utf8')
      // console.log('python返回值：')
      // console.log(pythonResponse);
      displayMessageBox(pythonResponse)
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
  const currentCodeValue = codearea.value;
  fs.writeFileSync(openedFilePath, currentCodeValue, "utf-8")
  saveNotice.classList.add("active")
  setTimeout("removeActive()", 1500);
  console.log(openedFilePath)
  sendToPython(openedFilePath);
});
  
// runBtn.dispatchEvent(new Event('mouseup'));

ipcRenderer.on("fileOpened", (event, { contents, filePath }) => {
    openedFilePath = filePath;
    document.getElementById('codearea').value = contents;
})

// 这里是对于保存成功提示去除active，取消显示
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

// // 这里是对于某个操作结束时出现的消息弹框，去除hidden，开始显示
// function removeHidden() {
//   messageDialog.classList.remove("hidden")
// }

// function addHidden() {
//   messageDialog.classList.add('hidden')
// }

// // 选择需要观察变动的节点
// const consoleLogText = document.getElementById('console-log-text');

// // 观察器的配置（需要观察什么变动）
// const config = { attributes: true, childList: true, subtree: true };

// // 当观察到变动时执行的回调函数
// const callback = function(mutationsList, observer) {
//     // Use traditional 'for loops' for IE 11
//     // 注意下面不能出现console.log否则会导致死循环
//     for(let mutation of mutationsList) {
//         if (mutation.type === 'childList') {
//             let lines = consoleLogText.innerHTML.split("\n");
//             // alert(lines)
//             // 文字内容的最后一行在lines.length - 2位置处，最后面的一行是空白
//             let lastLine = lines[lines.length - 2];
//             if (lines.indexOf('合好的音视频文件') != -1) {
//               // alert('合并完成！')
//               messageDialogContent = '合并完成！'
//               removeHidden()
//               setTimeout('addHidden()', 1000)
//             }
//         }
//         else if (mutation.type === 'attributes') {
//             alert('The ' + mutation.attributeName + ' attribute was modified.');
//         }
//     }
// };

// // 创建一个观察器实例并传入回调函数
// const observer = new MutationObserver(callback);

// // 以上述配置开始观察目标节点
// observer.observe(consoleLogText, config);

// // 之后，可停止观察
// // observer.disconnect(); 