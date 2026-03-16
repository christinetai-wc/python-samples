/**
 * 自學群組記錄器
 *
 * 功能：記錄自學 LINE 群組的所有訊息到 Google Drive
 * 每天一個資料夾，messages.txt + 附件
 *
 * 不做分類、不判斷角色、不猜主題，越笨越穩。
 */

// ===== 自學群組設定 =====
const STUDY_CONFIG = {
  // Google Drive 根資料夾名稱
  ROOT_FOLDER_NAME: '自學紀錄',

  // 群組 ID → 資料夾名稱對照表
  // 把 Bot 加進群組後，從 GAS 執行紀錄裡找到 groupId，填在這裡
  GROUPS: {
    // 'Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx': '一起學自學',
    // 'Cxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx': '另一個課程群組',
  }
};

/**
 * 判斷是否為自學群組
 */
function isStudyGroup(groupId) {
  return groupId && STUDY_CONFIG.GROUPS.hasOwnProperty(groupId);
}

/**
 * 取得群組的資料夾名稱
 */
function getStudyGroupName(groupId) {
  return STUDY_CONFIG.GROUPS[groupId] || groupId;
}

/**
 * 處理自學群組的訊息事件
 * 所有類型的訊息都記錄
 */
function handleStudyMessage(event) {
  const groupId = event.source.groupId;
  const groupName = getStudyGroupName(groupId);

  // 取得發言者名稱
  let senderName = '未知';
  try {
    const profile = getGroupMemberProfile(groupId, event.source.userId);
    senderName = profile.displayName || '未知';
  } catch (err) {
    console.log('取得發言者名稱失敗:', err);
  }

  const now = new Date();
  const dateStr = Utilities.formatDate(now, 'Asia/Taipei', 'yyyy.MM.dd');
  const timeStr = Utilities.formatDate(now, 'Asia/Taipei', 'yyyy.MM.dd HH:mm');
  const dateFolderName = Utilities.formatDate(now, 'Asia/Taipei', 'yyyy-MM-dd');

  const msg = event.message;
  let line = '';

  switch (msg.type) {
    case 'text':
      // 文字訊息：換行替換成 \n 存成一行
      const content = msg.text.replace(/\n/g, '\\n');
      line = timeStr + '|' + senderName + '|' + content;
      break;

    case 'image': {
      const filename = saveStudyMedia(groupId, dateFolderName, msg.id, 'image');
      line = timeStr + '|' + senderName + '|[image]' + filename;
      break;
    }

    case 'video': {
      const filename = saveStudyMedia(groupId, dateFolderName, msg.id, 'video');
      line = timeStr + '|' + senderName + '|[video]' + filename;
      break;
    }

    case 'audio': {
      const filename = saveStudyMedia(groupId, dateFolderName, msg.id, 'audio');
      line = timeStr + '|' + senderName + '|[audio]' + filename;
      break;
    }

    case 'file': {
      const filename = saveStudyMedia(groupId, dateFolderName, msg.id, 'file', msg.fileName);
      line = timeStr + '|' + senderName + '|[file]' + filename;
      break;
    }

    case 'sticker':
      // 貼圖：不記錄
      return;

    default:
      // 其他類型：記一個標記就好
      line = timeStr + '|' + senderName + '|[' + msg.type + ']';
      break;
  }

  if (line) {
    appendToMessagesFile(groupId, dateFolderName, line);
  }
}

/**
 * 取得群組成員的 profile
 */
function getGroupMemberProfile(groupId, userId) {
  const url = 'https://api.line.me/v2/bot/group/' + groupId + '/member/' + userId;
  const options = {
    method: 'get',
    headers: {
      'Authorization': 'Bearer ' + CONFIG.LINE_CHANNEL_ACCESS_TOKEN
    },
    muteHttpExceptions: true
  };
  const response = UrlFetchApp.fetch(url, options);
  return JSON.parse(response.getContentText());
}

/**
 * 下載 LINE 媒體檔案並存到 Google Drive
 * 回傳檔名
 */
function saveStudyMedia(groupId, dateFolderName, messageId, mediaType, originalFileName) {
  try {
    // 從 LINE 下載媒體
    const url = 'https://api-data.line.me/v2/bot/message/' + messageId + '/content';
    const options = {
      method: 'get',
      headers: {
        'Authorization': 'Bearer ' + CONFIG.LINE_CHANNEL_ACCESS_TOKEN
      },
      muteHttpExceptions: true
    };
    const response = UrlFetchApp.fetch(url, options);
    const blob = response.getBlob();

    // 決定檔名
    let filename;
    if (originalFileName) {
      // 檔案類型（如 PDF）保留原始檔名
      filename = originalFileName;
    } else {
      // 圖片/影片/音訊：用流水號
      const ext = getExtension(mediaType, blob.getContentType());
      const folder = getStudyDateFolder(groupId, dateFolderName);
      const existing = folder.getFiles();
      let count = 0;
      while (existing.hasNext()) {
        const f = existing.next();
        if (f.getName().startsWith(mediaType + '_')) count++;
      }
      filename = mediaType + '_' + String(count + 1).padStart(3, '0') + '.' + ext;
    }

    // 存到資料夾
    const folder = getStudyDateFolder(groupId, dateFolderName);

    // 檢查是否已有同名檔案，有的話加編號
    const existingFiles = folder.getFilesByName(filename);
    if (existingFiles.hasNext()) {
      const nameParts = filename.split('.');
      const ext = nameParts.pop();
      const base = nameParts.join('.');
      filename = base + '_' + messageId.substring(0, 6) + '.' + ext;
    }

    blob.setName(filename);
    folder.createFile(blob);

    return filename;
  } catch (err) {
    console.error('下載媒體失敗:', err);
    // 記錄失敗，留待重試
    logMediaFailure(groupId, dateFolderName, messageId, mediaType, originalFileName, err.message);
    return mediaType + '_FAILED_' + messageId;
  }
}

/**
 * 記錄媒體下載失敗，寫入 failed_media.tsv
 * 格式：messageId \t mediaType \t originalFileName \t error \t timestamp \t retried
 */
function logMediaFailure(groupId, dateFolderName, messageId, mediaType, originalFileName, errorMsg) {
  try {
    const folder = getStudyDateFolder(groupId, dateFolderName);
    const fileName = 'failed_media.tsv';
    const now = new Date().toISOString();
    const line = [messageId, mediaType, originalFileName || '', errorMsg, now, 'no'].join('\t');

    const files = folder.getFilesByName(fileName);
    if (files.hasNext()) {
      const file = files.next();
      const existing = file.getBlob().getDataAsString();
      file.setContent(existing + line + '\n');
    } else {
      const header = 'messageId\tmediaType\toriginalFileName\terror\ttimestamp\tretried\n';
      folder.createFile(fileName, header + line + '\n', 'text/plain');
    }
  } catch (e) {
    console.error('寫入 failed_media.tsv 也失敗了:', e);
  }
}

/**
 * 重試所有失敗的媒體下載
 * 手動執行：在 GAS 編輯器選 retryFailedMedia 然後按執行
 */
function retryFailedMedia() {
  const rootFolder = getOrCreateFolder_(null, STUDY_CONFIG.ROOT_FOLDER_NAME);

  let totalRetried = 0;
  let totalSuccess = 0;
  let totalFail = 0;

  // 遍歷所有群組資料夾
  const groupFolders = rootFolder.getFolders();
  while (groupFolders.hasNext()) {
    const groupFolder = groupFolders.next();
    const groupName = groupFolder.getName();

    // 反查 groupId
    let groupId = null;
    for (const gid in STUDY_CONFIG.GROUPS) {
      if (STUDY_CONFIG.GROUPS[gid] === groupName) {
        groupId = gid;
        break;
      }
    }
    if (!groupId) continue;

    // 遍歷日期資料夾
    const dateFolders = groupFolder.getFolders();
    while (dateFolders.hasNext()) {
      const dateFolder = dateFolders.next();
      const dateFolderName = dateFolder.getName();

      // 找 failed_media.tsv
      const failFiles = dateFolder.getFilesByName('failed_media.tsv');
      if (!failFiles.hasNext()) continue;

      const failFile = failFiles.next();
      const content = failFile.getBlob().getDataAsString();
      const lines = content.trim().split('\n');
      if (lines.length <= 1) continue; // 只有 header

      const header = lines[0];
      const newLines = [header];

      for (let i = 1; i < lines.length; i++) {
        const cols = lines[i].split('\t');
        if (cols.length < 6) { newLines.push(lines[i]); continue; }

        const [messageId, mediaType, originalFileName, error, timestamp, retried] = cols;

        if (retried === 'yes') {
          newLines.push(lines[i]);
          continue;
        }

        totalRetried++;
        console.log('重試: ' + dateFolderName + ' / ' + mediaType + ' / ' + messageId);

        try {
          const filename = saveStudyMedia(groupId, dateFolderName, messageId, mediaType, originalFileName || undefined);
          if (filename && !filename.includes('_FAILED_')) {
            // 成功！更新 messages.txt 裡的 FAILED 標記
            updateMessagesFileOnRetry(dateFolder, messageId, mediaType, filename);
            cols[5] = 'yes';
            newLines.push(cols.join('\t'));
            totalSuccess++;
            console.log('重試成功: ' + filename);
          } else {
            cols[3] = '重試仍失敗';
            cols[4] = new Date().toISOString();
            newLines.push(cols.join('\t'));
            totalFail++;
          }
        } catch (e) {
          cols[3] = '重試例外: ' + e.message;
          cols[4] = new Date().toISOString();
          newLines.push(cols.join('\t'));
          totalFail++;
        }
      }

      // 更新 failed_media.tsv
      failFile.setContent(newLines.join('\n') + '\n');
    }
  }

  console.log('重試完成: 共 ' + totalRetried + ' 筆, 成功 ' + totalSuccess + ', 失敗 ' + totalFail);
  return { retried: totalRetried, success: totalSuccess, fail: totalFail };
}

/**
 * 重試成功後，更新 messages.txt 裡的 FAILED 檔名
 */
function updateMessagesFileOnRetry(dateFolder, messageId, mediaType, newFilename) {
  try {
    const msgFiles = dateFolder.getFilesByName('messages.txt');
    if (!msgFiles.hasNext()) return;

    const msgFile = msgFiles.next();
    const content = msgFile.getBlob().getDataAsString();
    const failTag = mediaType + '_FAILED_' + messageId;

    if (content.includes(failTag)) {
      msgFile.setContent(content.replace(failTag, newFilename));
    }
  } catch (e) {
    console.error('更新 messages.txt 失敗:', e);
  }
}

/**
 * 根據媒體類型和 content type 決定副檔名
 */
function getExtension(mediaType, contentType) {
  const map = {
    'image/jpeg': 'jpg',
    'image/png': 'png',
    'image/gif': 'gif',
    'image/webp': 'webp',
    'video/mp4': 'mp4',
    'audio/m4a': 'm4a',
    'audio/mp4': 'm4a',
    'application/pdf': 'pdf',
  };
  if (map[contentType]) return map[contentType];

  // fallback
  switch (mediaType) {
    case 'image': return 'jpg';
    case 'video': return 'mp4';
    case 'audio': return 'm4a';
    default: return 'bin';
  }
}

/**
 * 追加一行到 messages.txt
 */
function appendToMessagesFile(groupId, dateFolderName, line) {
  const folder = getStudyDateFolder(groupId, dateFolderName);
  const fileName = 'messages.txt';

  const files = folder.getFilesByName(fileName);
  if (files.hasNext()) {
    // 追加到現有檔案
    const file = files.next();
    const existing = file.getBlob().getDataAsString();
    file.setContent(existing + line + '\n');
  } else {
    // 建立新檔案
    folder.createFile(fileName, line + '\n', 'text/plain');
  }
}

/**
 * 取得或建立 Google Drive 的日期資料夾
 * 結構：自學紀錄/群組名稱/yyyy-MM-dd/
 */
function getStudyDateFolder(groupId, dateFolderName) {
  const groupName = getStudyGroupName(groupId);

  // 取得或建立根資料夾
  const rootFolder = getOrCreateFolder_(null, STUDY_CONFIG.ROOT_FOLDER_NAME);
  // 取得或建立群組資料夾
  const groupFolder = getOrCreateFolder_(rootFolder, groupName);
  // 取得或建立日期資料夾
  const dateFolder = getOrCreateFolder_(groupFolder, dateFolderName);

  return dateFolder;
}

/**
 * 取得或建立子資料夾
 */
function getOrCreateFolder_(parent, name) {
  let root;
  if (parent) {
    const folders = parent.getFoldersByName(name);
    if (folders.hasNext()) return folders.next();
    return parent.createFolder(name);
  } else {
    // 在 My Drive 根目錄找
    const folders = DriveApp.getFoldersByName(name);
    if (folders.hasNext()) return folders.next();
    return DriveApp.createFolder(name);
  }
}
