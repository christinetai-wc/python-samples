/**
 * 吃藥提醒模組
 * - 每小時排程提醒
 * - 吃藥回報
 * - 漏吃追蹤
 */

// ===== 指令判斷 =====

function isMedicineTakenCommand(text) {
  const patterns = ['吃了', '吃了藥', '吃過藥', '吃過藥了', '已吃', '已吃藥', '吃過了', '藥吃了', '吃藥了'];
  return patterns.includes(text);
}

function hasMedicineTakenWithTime(text) {
  const prefixes = ['吃了', '吃了藥', '吃過藥', '吃過藥了', '已吃', '已吃藥', '吃過了', '藥吃了', '吃藥了'];
  for (const prefix of prefixes) {
    if (text.startsWith(prefix + ' ') && text.length > prefix.length + 1) return true;
  }
  return false;
}

function extractTimeFromMedicineCommand(text) {
  const prefixes = ['吃了藥', '吃過藥了', '吃過藥', '已吃藥', '吃藥了', '藥吃了', '吃過了', '已吃', '吃了'];
  for (const prefix of prefixes) {
    if (text.startsWith(prefix + ' ')) return text.substring(prefix.length + 1).trim();
  }
  return text;
}

// ===== 吃藥回報 =====

function handleMedicineTaken(reporter) {
  const now = new Date();
  const currentHour = parseInt(Utilities.formatDate(now, 'Asia/Taipei', 'HH'));
  const schedule = getAllMedicineSchedule();
  if (schedule.length === 0) return '📋 尚未設定吃藥時間';

  let closestSchedule = null;
  let minDiff = 24;
  for (const item of schedule) {
    const scheduleHour = parseInt(item.time.substring(0, 2));
    let diff = Math.abs(currentHour - scheduleHour);
    if (diff > 12) diff = 24 - diff;
    if (diff <= 2 && diff < minDiff) {
      minDiff = diff;
      closestSchedule = item;
    }
  }

  if (!closestSchedule) return '⚠️ 找不到最近的吃藥時段\n\n可以說：\n• /吃了 早上\n• /吃了 中午\n• /吃了 晚上\n• /吃了 睡前';
  return recordMedicinesAtTime(closestSchedule.time, closestSchedule.medicines, reporter);
}

function handleMedicineTakenAtTime(timeArg, reporter) {
  const schedule = getAllMedicineSchedule();
  if (schedule.length === 0) return '📋 尚未設定吃藥時間';

  let time = timeArg.trim();
  const keywords = {
    '早上': [6, 10], '早': [6, 10],
    '中午': [11, 14], '午': [11, 14],
    '下午': [14, 18],
    '晚上': [17, 21], '晚': [17, 21],
    '睡前': [20, 24], '夜': [20, 24]
  };

  let targetSchedule = null;

  if (keywords[time]) {
    const [startHour, endHour] = keywords[time];
    for (const item of schedule) {
      const scheduleHour = parseInt(item.time.substring(0, 2));
      if (scheduleHour >= startHour && scheduleHour < endHour) {
        targetSchedule = item;
        break;
      }
    }
    if (!targetSchedule) return `⚠️ ${time}沒有設定吃藥時間`;
  } else {
    if (time.length === 1) time = '0' + time + ':00';
    else if (time.length === 2) time = time + ':00';
    const targetHour = time.substring(0, 2);
    for (const item of schedule) {
      if (item.time.startsWith(targetHour)) { targetSchedule = item; break; }
    }
    if (!targetSchedule) return `⚠️ 找不到 ${time} 的吃藥時段`;
  }

  return recordMedicinesAtTime(targetSchedule.time, targetSchedule.medicines, reporter);
}

function recordMedicinesAtTime(time, medicines, reporter) {
  let recorded = [];
  let alreadyTaken = [];

  for (const med of medicines) {
    if (med.note && med.note.toLowerCase() === 'done') continue;
    if (isMedicineTakenToday(time, med.name)) {
      alreadyTaken.push(med.name);
    } else {
      recordMedicineTaken(time, med.name, reporter);
      recorded.push(med.name);
    }
  }

  let reply = '';
  if (recorded.length > 0) {
    reply = `✅ 已記錄 ${time} 吃藥\n`;
    for (const name of recorded) reply += `  ✓ ${name}\n`;
  }
  if (alreadyTaken.length > 0) {
    if (reply) reply += '\n';
    reply += `ℹ️ 已經記錄過：\n`;
    for (const name of alreadyTaken) reply += `  • ${name}\n`;
  }
  if (!reply) reply = '⚠️ 沒有藥物需要記錄';
  reply += '\n\n' + getMedicineScheduleText();
  return reply.trim();
}

// ===== 群組設定 =====

function getMedicineGroupId() {
  const props = PropertiesService.getScriptProperties();
  return props.getProperty('medicineGroupId') || '';
}

function setMedicineGroupId(groupId) {
  const props = PropertiesService.getScriptProperties();
  props.setProperty('medicineGroupId', groupId);
  console.log('已設定群組 ID:', groupId);
}

// ===== 時間表顯示 =====

function getMedicineScheduleText() {
  const schedule = getAllMedicineSchedule();
  if (schedule.length === 0) return '📋 尚未設定吃藥時間\n\n請在 Google Sheets「吃藥提醒」工作表中填入';

  const today = Utilities.formatDate(new Date(), 'Asia/Taipei', 'yyyy-MM-dd');
  let text = `💊 吃藥時間表 (${today})\n`;

  for (const item of schedule) {
    const activeMeds = item.medicines.filter(m => !m.note || m.note.toLowerCase() !== 'done');
    if (activeMeds.length === 0) continue;

    text += `\n⏰ ${item.time}`;
    for (const med of activeMeds) {
      const takenTime = getMedicineTakenTime(item.time, med.name);
      if (takenTime) {
        text += `\n  ✅ ${med.name} (${takenTime})`;
      } else {
        text += `\n  ⬜ ${med.name}`;
        if (med.note) text += ` (${med.note})`;
      }
    }
  }
  return text;
}

// ===== 排程提醒 =====

function sendMedicineReminder() {
  const now = new Date();
  const actualTime = Utilities.formatDate(now, 'Asia/Taipei', 'yyyy-MM-dd HH:mm:ss');
  const minutes = parseInt(Utilities.formatDate(now, 'Asia/Taipei', 'mm'));
  let targetHour = parseInt(Utilities.formatDate(now, 'Asia/Taipei', 'HH'));
  if (minutes >= 30) targetHour = (targetHour + 1) % 24;
  const targetTime = String(targetHour).padStart(2, '0') + ':00';

  console.log('=== 吃藥提醒執行 ===');
  console.log('實際執行時間:', actualTime);
  console.log('對應整點時間:', targetTime);

  const momLineId = findLineIdByName('媽媽');
  if (!momLineId) { console.log('❌ 找不到媽媽的 LINE ID'); return; }

  const schedule = getAllMedicineSchedule();
  let currentMeds = [];
  let missedMeds = [];

  for (const item of schedule) {
    const scheduleHour = parseInt(item.time.substring(0, 2));
    if (item.time.startsWith(targetTime.substring(0, 2))) {
      currentMeds = item.medicines
        .filter(m => !m.note || m.note.toLowerCase() !== 'done')
        .map(m => ({ ...m, time: item.time }));
    } else if (scheduleHour < targetHour) {
      for (const med of item.medicines) {
        if (med.note && med.note.toLowerCase() === 'done') continue;
        if (!isMedicineTakenToday(item.time, med.name)) {
          missedMeds.push({ ...med, time: item.time });
        }
      }
    }
  }

  if (currentMeds.length === 0 && missedMeds.length === 0) { console.log('沒有需要提醒的藥'); return; }

  if (currentMeds.length > 0) {
    let msg = `💊 ${targetTime} 吃藥時間到囉！\n`;
    for (const med of currentMeds) {
      msg += `• ${med.name}`;
      if (med.note) msg += ` (${med.note})`;
      msg += '\n';
    }
    pushMessage(momLineId, msg.trim());
  }

  if (missedMeds.length > 0) {
    let msg = `⚠️ 還沒吃的藥：\n`;
    for (const med of missedMeds) {
      msg += `• ${med.name} (${med.time})`;
      if (med.note) msg += ` - ${med.note}`;
      msg += '\n';
    }
    pushMessage(momLineId, msg.trim());

    const groupId = getMedicineGroupId();
    if (groupId) {
      let groupMsg = `⚠️ 媽媽還沒吃的藥：\n`;
      for (const med of missedMeds) {
        groupMsg += `• ${med.name} (${med.time})`;
        if (med.note) groupMsg += ` - ${med.note}`;
        groupMsg += '\n';
      }
      pushMessage(groupId, groupMsg.trim());
    }
  }
}

// ===== 觸發器管理 =====

function checkTriggers() {
  const triggers = ScriptApp.getProjectTriggers();
  console.log('=== 目前的觸發器 ===');
  console.log('觸發器數量:', triggers.length);
  for (const trigger of triggers) {
    console.log(`- ${trigger.getHandlerFunction()} (${trigger.getEventType()})`);
  }
  const hasReminder = triggers.some(t => t.getHandlerFunction() === 'sendMedicineReminder');
  console.log(hasReminder ? '\n✅ sendMedicineReminder 觸發器已設定' : '\n⚠️ 沒有設定 sendMedicineReminder 的觸發器！\n請執行 setupMedicineTrigger() 來設定');
}

function setupMedicineTrigger() {
  const triggers = ScriptApp.getProjectTriggers();
  for (const trigger of triggers) {
    if (trigger.getHandlerFunction() === 'sendMedicineReminder') {
      ScriptApp.deleteTrigger(trigger);
      console.log('已移除舊的觸發器');
    }
  }
  ScriptApp.newTrigger('sendMedicineReminder').timeBased().everyHours(1).create();
  console.log('✅ 已設定每小時執行 sendMedicineReminder');
}

// ===== 測試函數 =====

function testSendMedicineReminder() {
  const schedule = getAllMedicineSchedule();
  if (schedule.length === 0) { console.log('❌ 尚未設定吃藥時間'); return; }
  const momLineId = findLineIdByName('媽媽');
  if (!momLineId) { console.log('❌ 找不到媽媽的 LINE ID'); return; }
  const firstSchedule = schedule[0];
  const activeMeds = firstSchedule.medicines.filter(m => !m.note || m.note.toLowerCase() !== 'done');
  if (activeMeds.length === 0) { console.log('❌ 第一個時段沒有需要提醒的藥'); return; }
  let message = `🧪 測試提醒 (${firstSchedule.time})\n\n`;
  for (const med of activeMeds) {
    message += `• ${med.name}`;
    if (med.note) message += ` (${med.note})`;
    message += '\n';
  }
  const success = pushMessage(momLineId, message);
  console.log(success ? '✅ 測試提醒已私訊給媽媽' : '❌ 發送失敗');
}

function testMedicineReminder() {
  console.log('=== 測試吃藥提醒設定 ===');
  const momLineId = findLineIdByName('媽媽');
  console.log('媽媽 LINE ID:', momLineId || '❌ 未設定');
  const now = new Date();
  const currentHour = Utilities.formatDate(now, 'Asia/Taipei', 'HH:00');
  console.log('目前時間:', currentHour);
  const schedule = getAllMedicineSchedule();
  console.log('吃藥時間表（排除 Done）:');
  for (const item of schedule) {
    const activeMeds = item.medicines.filter(m => !m.note || m.note.toLowerCase() !== 'done');
    if (activeMeds.length > 0) console.log(`  ${item.time}: ${activeMeds.map(m => m.name).join('、')}`);
  }
}

function testGroupSetup() {
  console.log('=== 測試群組設定 ===\n');
  const momLineId = findLineIdByName('媽媽');
  console.log('1. 媽媽 LINE ID:', momLineId ? `✅ ${momLineId}` : '❌ 未設定');
  const groupId = getMedicineGroupId();
  console.log('2. 群組 ID:', groupId ? `✅ ${groupId}` : '❌ 未設定');
  if (momLineId) {
    const s = pushMessage(momLineId, '🧪 測試訊息：媽媽私訊正常');
    console.log('3. 私訊媽媽:', s ? '✅ 成功' : '❌ 失敗');
  }
  if (groupId) {
    const s = pushMessage(groupId, '🧪 測試訊息：群組通知正常');
    console.log('4. 發送群組:', s ? '✅ 成功' : '❌ 失敗');
  }
}
