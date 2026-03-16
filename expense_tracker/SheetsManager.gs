/**
 * Google Sheets 操作模組
 * - 帳目紀錄 CRUD
 * - 成員管理
 * - 結算計算
 */

/**
 * 取得 Spreadsheet
 */
function getSpreadsheet() {
  return SpreadsheetApp.openById(CONFIG.SPREADSHEET_ID);
}

/**
 * 確保工作表存在
 */
function ensureSheetsExist() {
  const ss = getSpreadsheet();
  const sheetNames = ss.getSheets().map(s => s.getName());

  // 帳目紀錄
  if (!sheetNames.includes('帳目紀錄')) {
    const ws = ss.insertSheet('帳目紀錄');
    ws.appendRow(['日期時間', '項目', '金額', '付款人', '參與者', '分攤方式', '圖片連結']);
  }

  // 家庭名單
  if (!sheetNames.includes('家庭名單')) {
    const ws = ss.insertSheet('家庭名單');
    ws.appendRow(['名稱', 'LINE_ID', '參與均分']);
  }

  // 轉帳紀錄
  if (!sheetNames.includes('轉帳紀錄')) {
    const ws = ss.insertSheet('轉帳紀錄');
    ws.appendRow(['日期時間', '轉出者', '轉入者', '金額', '備註']);
  }

  // 吃藥提醒
  if (!sheetNames.includes('吃藥提醒')) {
    const ws = ss.insertSheet('吃藥提醒');
    ws.appendRow(['時間', '藥名', '備註']);
    // 加入範例資料
    ws.appendRow(['08:00', '範例藥（請修改）', '飯後']);
  }

  // 吃藥紀錄
  if (!sheetNames.includes('吃藥紀錄')) {
    const ws = ss.insertSheet('吃藥紀錄');
    ws.appendRow(['日期', '時間', '藥名', '回報者', '回報時間']);
  }
}

/**
 * 新增一筆支出
 */
function addExpense(item, amount, payer, participants, splitType, imageUrl) {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('帳目紀錄');

  const now = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyy-MM-dd HH:mm');
  const participantsStr = participants.join(',');

  ws.appendRow([now, item, amount, payer, participantsStr, splitType, imageUrl || '']);
}

/**
 * 取得所有帳目
 */
function getAllExpenses() {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('帳目紀錄');

  const data = ws.getDataRange().getValues();

  if (data.length <= 1) {
    return [];
  }

  const headers = data[0];
  const records = [];

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const record = {};
    for (let j = 0; j < headers.length; j++) {
      record[headers[j]] = row[j];
    }
    records.push(record);
  }

  return records;
}

/**
 * 計算結算摘要
 * 新邏輯：總開銷 ÷ 所有成員 = 每人應負擔
 * 扣除已轉帳金額後，計算還需轉帳多少
 */
function getSummary() {
  const expenses = getAllExpenses();
  const existingTransfers = getAllTransfers();

  if (expenses.length === 0) {
    return {
      total: 0,
      paid: {},
      perPerson: 0,
      balance: {},
      transfers: [],
      completedTransfers: existingTransfers
    };
  }

  // 計算總開銷
  let total = 0;
  const paid = {};
  const allMembers = new Set();

  for (const exp of expenses) {
    const payer = exp['付款人'];
    const amount = Number(exp['金額']);
    const participants = String(exp['參與者']).split(',');

    total += amount;
    paid[payer] = (paid[payer] || 0) + amount;

    // 收集所有參與者
    for (let p of participants) {
      allMembers.add(p.trim());
    }
    allMembers.add(payer);
  }

  // 每人應負擔 = 總開銷 ÷ 成員數
  const memberCount = allMembers.size;
  const perPerson = total / memberCount;

  // 計算每人結餘（正=應收，負=應付）
  const balance = {};
  for (const person of allMembers) {
    balance[person] = (paid[person] || 0) - perPerson;
  }

  // 扣除已轉帳金額
  for (const t of existingTransfers) {
    const from = t['轉出者'];
    const to = t['轉入者'];
    const amount = Number(t['金額']);

    // 轉出者的債務減少（balance 變正）
    if (balance[from] !== undefined) {
      balance[from] += amount;
    }
    // 轉入者的債權減少（balance 變負）
    if (balance[to] !== undefined) {
      balance[to] -= amount;
    }
  }

  // 計算還需轉帳明細
  const transfers = calculateTransfers(balance);

  return {
    total: total,
    paid: paid,
    perPerson: perPerson,
    memberCount: memberCount,
    balance: balance,
    transfers: transfers,
    completedTransfers: existingTransfers
  };
}

/**
 * 計算最少轉帳次數的轉帳明細
 */
function calculateTransfers(balance) {
  // 分成債務人（負數）和債權人（正數）
  const debtors = [];  // 應付的人
  const creditors = []; // 應收的人

  for (const [person, amount] of Object.entries(balance)) {
    if (amount < -0.5) {  // 允許小誤差
      debtors.push({ name: person, amount: Math.abs(amount) });
    } else if (amount > 0.5) {
      creditors.push({ name: person, amount: amount });
    }
  }

  // 排序：金額大的優先
  debtors.sort((a, b) => b.amount - a.amount);
  creditors.sort((a, b) => b.amount - a.amount);

  const transfers = [];

  // 配對轉帳
  let i = 0, j = 0;
  while (i < debtors.length && j < creditors.length) {
    const debtor = debtors[i];
    const creditor = creditors[j];
    const transferAmount = Math.min(debtor.amount, creditor.amount);

    if (transferAmount > 0.5) {
      transfers.push({
        from: debtor.name,
        to: creditor.name,
        amount: Math.round(transferAmount)
      });
    }

    debtor.amount -= transferAmount;
    creditor.amount -= transferAmount;

    if (debtor.amount < 0.5) i++;
    if (creditor.amount < 0.5) j++;
  }

  return transfers;
}

/**
 * 刪除最後一筆帳目
 * @returns {Object|null} 被刪除的紀錄
 */
function deleteLastExpense() {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('帳目紀錄');

  const data = ws.getDataRange().getValues();

  // 第一行是標題，至少要有兩行才有資料
  if (data.length < 2) {
    return null;
  }

  // 取得最後一行的資料
  const lastRowNum = data.length;
  const lastRow = data[lastRowNum - 1];
  const headers = data[0];

  // 建立紀錄 dict
  const deletedRecord = {};
  for (let i = 0; i < headers.length; i++) {
    deletedRecord[headers[i]] = lastRow[i];
  }

  // 刪除該行
  ws.deleteRow(lastRowNum);

  // 如果有圖片，一併刪除
  const imageUrl = deletedRecord['圖片連結'];
  let imageDeleted = false;

  if (imageUrl && imageUrl.includes('drive.google.com')) {
    imageDeleted = deleteImageFromDrive(imageUrl);
  }

  // 組合回覆訊息
  let reply = '🗑️ 已刪除\n';
  reply += `📝 ${deletedRecord['項目'] || '?'}\n`;
  reply += `💰 $${Number(deletedRecord['金額'] || 0).toLocaleString()}\n`;
  reply += `💳 ${deletedRecord['付款人'] || '?'} 付款`;

  if (imageUrl) {
    if (imageDeleted) {
      reply += '\n🖼️ 圖片已刪除';
    } else {
      reply += '\n⚠️ 圖片刪除失敗';
    }
  }

  return reply;
}

// ===== 轉帳紀錄 =====

/**
 * 新增轉帳紀錄
 * @param {string} from - 轉出者
 * @param {string} to - 轉入者
 * @param {number} amount - 金額
 * @param {string} note - 備註（可選）
 */
function addTransfer(from, to, amount, note) {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('轉帳紀錄');

  const now = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyy-MM-dd HH:mm');
  ws.appendRow([now, from, to, amount, note || '']);
}

/**
 * 取得所有轉帳紀錄
 */
function getAllTransfers() {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('轉帳紀錄');

  const data = ws.getDataRange().getValues();

  if (data.length <= 1) {
    return [];
  }

  const headers = data[0];
  const records = [];

  for (let i = 1; i < data.length; i++) {
    const row = data[i];
    const record = {};
    for (let j = 0; j < headers.length; j++) {
      record[headers[j]] = row[j];
    }
    records.push(record);
  }

  return records;
}

/**
 * 刪除最後一筆轉帳
 */
function deleteLastTransfer() {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('轉帳紀錄');

  const data = ws.getDataRange().getValues();

  if (data.length < 2) {
    return null;
  }

  const lastRowNum = data.length;
  const lastRow = data[lastRowNum - 1];
  const headers = data[0];

  const deletedRecord = {};
  for (let i = 0; i < headers.length; i++) {
    deletedRecord[headers[i]] = lastRow[i];
  }

  ws.deleteRow(lastRowNum);

  return deletedRecord;
}

// ===== 成員管理 =====

/**
 * 新增成員
 * @param {string} name - 成員名稱
 * @param {string} lineId - LINE ID
 * @param {boolean} joinSplit - 是否參與均分（預設 true）
 */
function addMember(name, lineId, joinSplit = true) {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('家庭名單');

  // 檢查是否已存在
  const data = ws.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][1] === lineId) {
      // 更新名稱
      ws.getRange(i + 1, 1).setValue(name);
      // 保留原本的參與均分設定（除非明確指定）
      return;
    }
  }

  // 新增（預設參與均分）
  ws.appendRow([name, lineId, joinSplit ? '是' : '否']);
}

/**
 * 根據 LINE ID 找成員名稱
 */
function findMemberByLineId(lineId) {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('家庭名單');

  const data = ws.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][1] === lineId) {
      return data[i][0];
    }
  }

  return null;
}

/**
 * 取得所有成員
 */
function getAllMembers() {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('家庭名單');

  const data = ws.getDataRange().getValues();
  const members = [];

  for (let i = 1; i < data.length; i++) {
    const joinSplit = data[i][2];
    // 「否」或「不參與」才是不參與，其他都視為參與
    const isJoinSplit = !(joinSplit === '否' || joinSplit === '不參與' || joinSplit === false);

    members.push({
      name: data[i][0],
      lineId: data[i][1],
      joinSplit: isJoinSplit
    });
  }

  return members;
}

/**
 * 根據名稱找成員的 LINE ID
 */
function findLineIdByName(name) {
  const members = getAllMembers();
  for (const m of members) {
    if (m.name === name) {
      return m.lineId;
    }
  }
  return null;
}

// ===== 吃藥提醒 =====

/**
 * 取得指定時間的藥物清單
 * @param {string} time - 時間格式 "HH:00"
 * @returns {Array} [{name, note}, ...]
 */
function getMedicinesByTime(time) {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('吃藥提醒');

  const data = ws.getDataRange().getValues();
  const medicines = [];

  // 從傳入的時間提取小時數字（例如 "08:00" -> 8）
  const targetHour = parseInt(time.substring(0, 2));

  for (let i = 1; i < data.length; i++) {
    const rowTime = data[i][0];
    // 處理不同格式的時間（可能是 Date 物件或字串）
    let timeStr = '';
    if (rowTime instanceof Date) {
      timeStr = Utilities.formatDate(rowTime, 'Asia/Taipei', 'HH:mm');
    } else {
      timeStr = String(rowTime).trim();
    }

    // 提取工作表中的小時數字（支援 "8:00" 和 "08:00" 兩種格式）
    const sheetHour = parseInt(timeStr.split(':')[0]);

    // 比對小時
    if (sheetHour === targetHour) {
      medicines.push({
        name: data[i][1] || '',
        note: data[i][2] || ''
      });
    }
  }

  return medicines;
}

/**
 * 取得所有吃藥時間
 */
function getAllMedicineTimes() {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('吃藥提醒');

  const data = ws.getDataRange().getValues();
  const times = [];

  for (let i = 1; i < data.length; i++) {
    const rowTime = data[i][0];
    let timeStr = '';
    if (rowTime instanceof Date) {
      timeStr = Utilities.formatDate(rowTime, 'Asia/Taipei', 'HH:mm');
    } else {
      timeStr = String(rowTime).trim();
    }
    if (timeStr && !times.includes(timeStr)) {
      times.push(timeStr);
    }
  }

  return times.sort();
}

/**
 * 取得完整吃藥時間表（含藥品）
 * @returns {Array} [{time: "08:00", medicines: [{name, note}, ...]}, ...]
 */
function getAllMedicineSchedule() {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('吃藥提醒');

  const data = ws.getDataRange().getValues();
  const scheduleMap = {};

  for (let i = 1; i < data.length; i++) {
    const rowTime = data[i][0];
    let timeStr = '';
    if (rowTime instanceof Date) {
      timeStr = Utilities.formatDate(rowTime, 'Asia/Taipei', 'HH:mm');
    } else {
      timeStr = String(rowTime).trim();
    }

    if (!timeStr) continue;

    // 統一轉成數字小時作為 key，確保 8:00 和 08:00 視為相同
    const hour = parseInt(timeStr.split(':')[0]);
    const normalizedTime = String(hour).padStart(2, '0') + ':00';

    if (!scheduleMap[normalizedTime]) {
      scheduleMap[normalizedTime] = [];
    }

    scheduleMap[normalizedTime].push({
      name: data[i][1] || '',
      note: data[i][2] || ''
    });
  }

  // 轉成陣列並排序
  const schedule = [];
  for (const time of Object.keys(scheduleMap).sort()) {
    schedule.push({
      time: time,
      medicines: scheduleMap[time]
    });
  }

  return schedule;
}

/**
 * 記錄吃藥
 * @param {string} time - 吃藥時間 "HH:00"
 * @param {string} medicineName - 藥名
 * @param {string} reporter - 回報者
 */
function recordMedicineTaken(time, medicineName, reporter) {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('吃藥紀錄');

  const now = new Date();
  const today = Utilities.formatDate(now, 'Asia/Taipei', 'yyyy-MM-dd');
  const reportTime = Utilities.formatDate(now, 'Asia/Taipei', 'HH:mm');

  ws.appendRow([today, time, medicineName, reporter, reportTime]);
}

/**
 * 取得今日已吃的藥
 * @returns {Array} [{time, name}, ...]
 */
function getTodayMedicineTaken() {
  ensureSheetsExist();

  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('吃藥紀錄');

  const data = ws.getDataRange().getValues();
  const today = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyy-MM-dd');

  const taken = [];
  for (let i = 1; i < data.length; i++) {
    const rowDate = data[i][0];
    let dateStr = '';
    if (rowDate instanceof Date) {
      dateStr = Utilities.formatDate(rowDate, 'Asia/Taipei', 'yyyy-MM-dd');
    } else {
      dateStr = String(rowDate).trim();
    }

    if (dateStr === today) {
      // 處理時間欄位（可能是 Date 物件或字串）
      const rowTime = data[i][1];
      let timeStr = '';
      if (rowTime instanceof Date) {
        timeStr = Utilities.formatDate(rowTime, 'Asia/Taipei', 'HH:mm');
      } else {
        timeStr = String(rowTime || '').trim();
      }

      // 處理回報時間欄位
      const rowReportTime = data[i][4];
      let reportTimeStr = '';
      if (rowReportTime instanceof Date) {
        reportTimeStr = Utilities.formatDate(rowReportTime, 'Asia/Taipei', 'HH:mm');
      } else {
        reportTimeStr = String(rowReportTime || '').trim();
      }

      taken.push({
        time: timeStr,
        name: String(data[i][2] || '').trim(),
        reportTime: reportTimeStr
      });
    }
  }

  return taken;
}

/**
 * 檢查某個時段的藥是否已吃
 * @param {string} time - 時間 "HH:00" 或 "HH:mm"
 * @param {string} medicineName - 藥名
 * @returns {boolean}
 */
function isMedicineTakenToday(time, medicineName) {
  const taken = getTodayMedicineTaken();
  const hour = parseInt(time.split(':')[0]);
  const targetName = String(medicineName).trim();

  for (const t of taken) {
    const takenHour = parseInt(t.time.split(':')[0]);
    const takenName = String(t.name).trim();
    if (takenHour === hour && takenName === targetName) {
      return true;
    }
  }
  return false;
}

/**
 * 取得某個時段藥物的回報時間
 * @param {string} time - 時間 "HH:00" 或 "HH:mm"
 * @param {string} medicineName - 藥名
 * @returns {string|null} 回報時間 "HH:mm" 或 null
 */
function getMedicineTakenTime(time, medicineName) {
  const taken = getTodayMedicineTaken();
  const hour = parseInt(time.split(':')[0]);
  const targetName = String(medicineName).trim();

  for (const t of taken) {
    const takenHour = parseInt(t.time.split(':')[0]);
    const takenName = String(t.name).trim();
    if (takenHour === hour && takenName === targetName) {
      return t.reportTime || null;
    }
  }
  return null;
}

// ===== 測試函數 =====

/**
 * 測試 Sheets 操作
 */
function testSheets() {
  // 測試新增
  addExpense('測試項目', 100, '測試者', ['測試者'], '均分', '');

  // 測試讀取
  const expenses = getAllExpenses();
  console.log('帳目數量:', expenses.length);

  // 測試結算
  const summary = getSummary();
  console.log('結算:', JSON.stringify(summary));
}

/**
 * 測試吃藥提醒工作表
 */
function testMedicineSheet() {
  console.log('=== 測試吃藥提醒工作表 ===');

  const times = getAllMedicineTimes();
  console.log('所有吃藥時間:', times);

  for (const time of times) {
    const meds = getMedicinesByTime(time);
    console.log(`${time}:`, JSON.stringify(meds));
  }
}

/**
 * 測試今日吃藥紀錄
 */
function testTodayMedicineTaken() {
  console.log('=== 測試今日吃藥紀錄 ===');

  const taken = getTodayMedicineTaken();
  console.log('今日已吃藥數量:', taken.length);

  for (const t of taken) {
    console.log(`  ${t.time} - ${t.name}`);
  }

  // 測試打勾比對
  const schedule = getAllMedicineSchedule();
  console.log('\n吃藥時間表打勾狀態:');
  for (const item of schedule) {
    console.log(`⏰ ${item.time}`);
    for (const med of item.medicines) {
      const isTaken = isMedicineTakenToday(item.time, med.name);
      console.log(`  ${isTaken ? '✅' : '⬜'} ${med.name}`);
    }
  }
}

// ===== 群組 ID 自動記錄 =====

/**
 * 自動記錄群組 ID 到「群組清單」sheet（不重複）
 */
function logGroupId(groupId) {
  const ss = getSpreadsheet();
  let ws = ss.getSheetByName('群組清單');
  if (!ws) {
    ws = ss.insertSheet('群組清單');
    ws.appendRow(['群組ID', '首次偵測時間', '備註']);
  }

  const data = ws.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === groupId) return;  // 已存在，不重複寫入
  }

  const now = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyy-MM-dd HH:mm');
  ws.appendRow([groupId, now, '']);
}

/**
 * 查詢群組類型（從「群組清單」sheet 的備註欄）
 * 備註欄填：FlashCard / 分帳 / 自學
 * @returns {string} 備註內容（空字串表示未設定）
 */
function getGroupType(groupId) {
  const ss = getSpreadsheet();
  const ws = ss.getSheetByName('群組清單');
  if (!ws) return '';

  const data = ws.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === groupId) {
      return String(data[i][2] || '').trim();
    }
  }
  return '';
}

/**
 * 自動記錄使用者 ID 到「使用者清單」sheet（不重複，只記第一次出現的來源群組）
 */
function logUserId(userId, source) {
  const ss = getSpreadsheet();
  let ws = ss.getSheetByName('使用者清單');
  if (!ws) {
    ws = ss.insertSheet('使用者清單');
    ws.appendRow(['LINE_USER_ID', '首次來源', '首次偵測時間', '備註']);
  }

  const data = ws.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][0] === userId) return;  // 已存在，不重複寫入
  }

  const now = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyy-MM-dd HH:mm');
  ws.appendRow([userId, source, now, '']);
}
