/**
 * 住院費用分帳模組
 * - 文字記帳 / AI 記帳
 * - 收據圖片 OCR
 * - 轉帳紀錄
 * - 結算查詢
 */

function isExpenseUser(userId) {
  // 查「家庭名單」sheet，有這個 LINE ID 就是分帳使用者
  return userId && !!findMemberByLineId(userId);
}

// 等待收據的群組（使用 PropertiesService 存儲）
function getPendingReceipts() {
  const props = PropertiesService.getScriptProperties();
  const data = props.getProperty('pendingReceipts');
  return data ? JSON.parse(data) : {};
}

function setPendingReceipts(data) {
  const props = PropertiesService.getScriptProperties();
  props.setProperty('pendingReceipts', JSON.stringify(data));
}

/**
 * 分帳 + 吃藥的統一入口（從 doPost 分派過來）
 */
function handleExpenseOrMedicineMessage(event) {
  if (event.message.type === 'text') {
    handleTextMessage(event);
  } else if (event.message.type === 'image') {
    handleImageMessage(event);
  }
}

/**
 * 處理文字訊息（記帳 + 吃藥指令）
 */
function handleTextMessage(event) {
  let text = event.message.text.trim();
  const userId = event.source.userId;

  const isGroup = event.source.type === 'group' || event.source.type === 'room';
  const chatId = event.source.groupId || event.source.roomId || userId;

  // 群組中只處理 / 或 @ 開頭的指令
  let isCommand = false;
  if (text.startsWith('/')) {
    text = text.substring(1).trim();
    isCommand = true;
  } else if (text.startsWith('@')) {
    const spaceIndex = text.indexOf(' ');
    if (spaceIndex > 0) {
      text = text.substring(spaceIndex + 1).trim();
      isCommand = true;
    }
  }
  if (isGroup && !isCommand) return;
  if (!text) return;

  const senderName = findMemberByLineId(userId) || '我';
  let reply = null;

  // === 分帳指令 ===
  if (text === '結算' || text === '統計') {
    reply = getSummaryText();
  } else if (text === '帳目' || text === '紀錄') {
    reply = getRecentExpenses();
  } else if (text === '刪除' || text === '刪除最後一筆') {
    reply = deleteLastExpense();
  } else if (text === '收據' || text === '圖片') {
    if (isGroup) {
      const pending = getPendingReceipts();
      pending[chatId] = new Date().getTime() + 120000;
      setPendingReceipts(pending);
      reply = '📷 請在 2 分鐘內傳送收據照片';
    } else {
      reply = '📷 請直接傳送收據照片';
    }
  } else if (text === '說明' || text === '幫助') {
    reply = getHelpText();

  // === 吃藥指令 ===
  } else if (text === '設定提醒群組') {
    if (isGroup) {
      setMedicineGroupId(chatId);
      reply = '✅ 已設定此群組為吃藥提醒群組';
    } else {
      reply = '❌ 請在群組中使用此指令';
    }
  } else if (text === '吃藥時間') {
    reply = getMedicineScheduleText();
  } else if (isMedicineTakenCommand(text)) {
    reply = handleMedicineTaken(senderName);
  } else if (hasMedicineTakenWithTime(text)) {
    const timeArg = extractTimeFromMedicineCommand(text);
    reply = handleMedicineTakenAtTime(timeArg, senderName);

  // === 轉帳指令 ===
  } else if (text.startsWith('轉帳') || text.startsWith('還款')) {
    reply = handleTransfer(text, senderName);
  } else if (text === '刪除轉帳') {
    reply = handleDeleteTransfer();
  } else if (text === '轉帳紀錄') {
    reply = getTransferHistory();

  // === 記帳文字解析 ===
  } else {
    const expense = parseExpense(text, senderName);
    if (expense) {
      const finalExpense = expense.amount > 0 ? expense : parseWithAI(text, senderName);
      if (finalExpense && finalExpense.amount > 0) {
        addExpense(finalExpense.item, finalExpense.amount, finalExpense.payer, finalExpense.participants, finalExpense.splitType);
        reply = formatExpenseConfirm(finalExpense);
      } else if (isGroup) {
        return;
      } else {
        reply = '❓ 無法理解\n\n試試這樣說：\n• /午餐600均分\n• /掛號費150 大哥付\n• /藥費500 二姐出';
      }
    } else if (!isGroup) {
      reply = '❓ 無法理解\n\n試試這樣說：\n• /午餐600均分\n• /掛號費150 大哥付\n• /藥費500 二姐出';
    }
  }

  if (reply) {
    replyMessage(event.replyToken, reply);
  }
}

/**
 * 處理圖片訊息（收據 OCR）
 */
function handleImageMessage(event) {
  const userId = event.source.userId;
  const messageId = event.message.id;
  const isGroup = event.source.type === 'group' || event.source.type === 'room';
  const chatId = event.source.groupId || event.source.roomId || userId;

  if (isGroup) {
    const pending = getPendingReceipts();
    if (!pending[chatId]) return;
    if (new Date().getTime() > pending[chatId]) {
      delete pending[chatId];
      setPendingReceipts(pending);
      return;
    }
    delete pending[chatId];
    setPendingReceipts(pending);
  }

  let reply = '';
  try {
    const imageBlob = downloadLineImage(messageId);
    const imageUrl = uploadImageToDrive(imageBlob, messageId);
    const ocrResult = extractAmountFromImage(imageBlob);
    const senderName = findMemberByLineId(userId) || '我';

    if (ocrResult.success) {
      const itemName = ocrResult.items && ocrResult.items.length > 0 ? ocrResult.items.join('、') : '收據';
      const defaultParticipants = getDefaultParticipants();
      addExpense(itemName, ocrResult.amount, senderName, defaultParticipants, '均分', imageUrl);
      reply = `✅ 已記錄\n📝 ${itemName}\n💰 $${ocrResult.amount.toLocaleString()}\n💳 ${senderName} 付款\n👥 ${defaultParticipants.join('、')} 均分`;
      if (imageUrl) reply += '\n📎 已附上收據圖片';
    } else {
      const defaultParticipants = getDefaultParticipants();
      addExpense('待補項目', 0, senderName, defaultParticipants, '均分', imageUrl);
      reply = '⚠️ 無法辨識金額\n\n✅ 已記錄「待補項目」\n請稍後在 Google Sheets 補充金額';
      if (imageUrl) reply += '\n📎 已附上收據圖片';
    }
  } catch (error) {
    console.error('圖片處理錯誤:', error);
    reply = '⚠️ 圖片處理失敗\n請手動輸入';
  }

  replyMessage(event.replyToken, reply);
}

// ===== 輔助函數 =====

function getSummaryText() {
  const summary = getSummary();
  if (summary.total === 0) return '📊 目前沒有帳目紀錄';

  let lines = ['📊 結算摘要\n'];
  lines.push(`💰 總開銷：$${summary.total.toLocaleString()}`);
  lines.push(`👥 成員數：${summary.memberCount} 人`);
  lines.push(`📊 每人應付：$${Math.round(summary.perPerson).toLocaleString()}`);

  lines.push('\n💳 各人已付：');
  for (const [person, amount] of Object.entries(summary.paid)) {
    lines.push(`  ${person}：$${amount.toLocaleString()}`);
  }

  if (summary.completedTransfers && summary.completedTransfers.length > 0) {
    lines.push('\n✅ 已轉帳：');
    for (const t of summary.completedTransfers) {
      lines.push(`  ${t['轉出者']} → ${t['轉入者']}：$${Number(t['金額']).toLocaleString()}`);
    }
  }

  if (summary.transfers && summary.transfers.length > 0) {
    lines.push('\n💸 還需轉帳：');
    for (const t of summary.transfers) {
      lines.push(`  ${t.from} → ${t.to}：$${t.amount.toLocaleString()}`);
    }
  } else {
    lines.push('\n✅ 已結清，無需轉帳');
  }

  return lines.join('\n');
}

function getRecentExpenses() {
  const expenses = getAllExpenses();
  if (expenses.length === 0) return '📝 目前沒有帳目紀錄';

  const recent = expenses.slice(-10).reverse();
  let lines = ['📝 最近帳目\n'];
  for (const exp of recent) {
    lines.push(`• ${exp['項目']} $${Number(exp['金額']).toLocaleString()} (${exp['付款人']}付)`);
  }
  const total = expenses.reduce((sum, e) => sum + Number(e['金額']), 0);
  lines.push(`\n總計：$${total.toLocaleString()}`);
  return lines.join('\n');
}

function getHelpText() {
  return `📖 使用說明

【記帳】用 / 開頭
• /午餐 750
• /掛號費 150 大哥付
• /藥費 500 二姐出

【轉帳】記錄已完成的轉帳
• /轉帳 5000 大哥（我給大哥）
• /轉帳 5000 二姐給大哥
• /轉帳紀錄 - 查看紀錄
• /刪除轉帳 - 刪除最後一筆

【查詢】
• /結算 - 每人應付/應收
• /帳目 - 最近紀錄
• /刪除 - 刪除最後一筆
• /說明 - 顯示此說明

【收據】
• /收據 → 2分鐘內傳圖片

【吃藥提醒】
• /吃藥時間 - 查看時間表（✅已吃 ⬜未吃）
• /吃了 - 回報吃藥（前後2小時內）
• /吃了 早上 - 回報早上的藥
• /吃了 晚上 - 回報晚上的藥
• /吃了 睡前 - 回報睡前的藥
• /設定提醒群組 - 設定提醒群組`;
}

function formatExpenseConfirm(data) {
  const participantsStr = data.participants.join('、');
  let msg = '✅ 已記錄\n';
  msg += `📝 ${data.item}\n`;
  msg += `💰 $${data.amount.toLocaleString()}\n`;
  msg += `💳 ${data.payer} 付款\n`;
  msg += `👥 ${participantsStr} ${data.splitType}`;
  if (data.splitType === '均分' && data.participants.length > 1) {
    const share = data.amount / data.participants.length;
    msg += `\n📊 每人 $${Math.round(share).toLocaleString()}`;
  }
  return msg;
}

function formatOcrResult(result) {
  return `💰 辨識金額：$${result.amount.toLocaleString()}
${result.items ? '📋 ' + result.items.join('、') : ''}

請補充項目名稱：
/項目名稱 ${result.amount}`;
}

// ===== 轉帳功能 =====

function handleTransfer(text, senderName) {
  text = text.replace(/^(轉帳|還款)\s*/, '').trim();
  let amount, from, to;
  let match = text.match(/^(\d+(?:\.\d+)?)\s+(.+?)給(.+)$/);
  if (match) {
    amount = parseFloat(match[1]); from = match[2].trim(); to = match[3].trim();
  } else {
    match = text.match(/^(\d+(?:\.\d+)?)\s+(\S+)\s+(\S+)$/);
    if (match) {
      amount = parseFloat(match[1]); from = match[2].trim(); to = match[3].trim();
    } else {
      match = text.match(/^(\d+(?:\.\d+)?)\s+(\S+)$/);
      if (match) {
        amount = parseFloat(match[1]); from = senderName; to = match[2].trim();
      }
    }
  }
  if (!match) return '❓ 格式錯誤\n\n正確格式：\n• /轉帳 5000 大哥（我給大哥）\n• /轉帳 5000 二姐給大哥\n• /轉帳 5000 二姐 大哥';
  if (amount <= 0) return '❓ 金額必須大於 0';
  if (from === to) return '❓ 轉出者和轉入者不能相同';
  addTransfer(from, to, amount, '');
  return `✅ 已記錄轉帳\n💸 ${from} → ${to}：$${amount.toLocaleString()}`;
}

function handleDeleteTransfer() {
  const deleted = deleteLastTransfer();
  if (!deleted) return '📝 目前沒有轉帳紀錄';
  return `🗑️ 已刪除轉帳\n💸 ${deleted['轉出者']} → ${deleted['轉入者']}：$${Number(deleted['金額']).toLocaleString()}`;
}

function getTransferHistory() {
  const transfers = getAllTransfers();
  if (transfers.length === 0) return '📝 目前沒有轉帳紀錄';
  let lines = ['💸 轉帳紀錄\n'];
  const recent = transfers.slice(-10).reverse();
  for (const t of recent) {
    lines.push(`• ${t['轉出者']} → ${t['轉入者']}：$${Number(t['金額']).toLocaleString()}`);
  }
  const total = transfers.reduce((sum, t) => sum + Number(t['金額']), 0);
  lines.push(`\n總計：$${total.toLocaleString()}`);
  return lines.join('\n');
}

// 測試
function testSummary() {
  console.log('=== 測試結算 ===\n');
  const summary = getSummary();
  console.log('結算數據:', JSON.stringify(summary, null, 2));
  console.log('\n=== 顯示文字 ===\n');
  console.log(getSummaryText());
}
