/**
 * FlashCard 家長群組模組
 * - 自動記錄家長 LINE User ID + 顯示名稱到 Sheet
 * - 不回覆任何訊息，只靜靜記錄
 */

/**
 * FlashCard 家長群組訊息處理：記錄 userId + displayName 到「FlashCard名單」sheet
 */
function handleFlashCardMessage(event) {
  const userId = event.source.userId;
  const groupId = event.source.groupId;
  if (!userId) return;

  // 取得顯示名稱
  let displayName = '未知';
  try {
    const profile = getGroupMemberProfile(groupId, userId);
    displayName = profile.displayName || '未知';
  } catch(e) {
    console.warn('取得家長名稱失敗:', e);
  }

  // 寫入 sheet（不重複）
  const ss = getSpreadsheet();
  let ws = ss.getSheetByName('FlashCard名單');
  if (!ws) {
    ws = ss.insertSheet('FlashCard名單');
    ws.appendRow(['LINE顯示名稱', 'LINE_USER_ID', '首次發言', '學生名稱', '已登記Firebase']);
  }

  const data = ws.getDataRange().getValues();
  for (let i = 1; i < data.length; i++) {
    if (data[i][1] === userId) {
      // 已存在，更新名稱就好
      ws.getRange(i + 1, 1).setValue(displayName);
      return;
    }
  }

  // 新增
  const now = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyy-MM-dd HH:mm');
  ws.appendRow([displayName, userId, now, '', '']);
}
