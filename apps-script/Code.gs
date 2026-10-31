/**
 * Radler price reports: receiver for the "Report a different price" form.
 * Runs as a Google Apps Script web app under the site owner's account (free).
 *
 * For each valid report it
 *   1. saves the photos privately to the owner's Google Drive ("Radler price reports" folder),
 *   2. emails the report with the photos attached to OWNER_EMAIL,
 *   3. answers {ok:true} only after the report has been stored.
 * No keys or secrets are needed; the web app URL is a public endpoint, like a form address.
 * Reports never change the public price data (data.json).
 *
 * Deploy: Deploy → New deployment → Web app → Execute as: Me, Who has access: Anyone.
 */
const OWNER_EMAIL = 'stepanenkon010@gmail.com';
const SUBJECT = 'New Radler Price Information';
const FOLDER_NAME = 'Radler price reports';
const CHAINS = ['REWE', 'Lidl', 'Kaufland', 'ALDI Süd', 'Penny'];
const MAX_FILES = 10;
const MAX_TOTAL_BYTES = 10 * 1024 * 1024;
const MIN_FILL_MS = 3000;          // faster than this after opening the form = bot
const MAX_REPORTS_PER_HOUR = 30;   // global flood limit

function doGet() {
  return json_({ ok: true, service: 'radler-price-reports' });
}

function doPost(e) {
  try {
    let d;
    try { d = JSON.parse(e.postData.contents); } catch (err) { return fail_('bad_request', 'Invalid request.'); }

    // Spam traps: hidden field filled in, or form submitted implausibly fast. Pretend success.
    if (d.website || (typeof d.fillMs === 'number' && d.fillMs < MIN_FILL_MS)) return json_({ ok: true });

    const cache = CacheService.getScriptCache();
    const id = String(d.id || '');
    if (!/^[A-Za-z0-9-]{8,64}$/.test(id)) return fail_('bad_request', 'Invalid request.');
    if (cache.get('done:' + id)) return json_({ ok: true, duplicate: true });  // retry of an accepted report

    const hourKey = 'n:' + Utilities.formatDate(new Date(), 'UTC', 'yyyyMMddHH');
    const n = Number(cache.get(hourKey) || 0);
    if (n >= MAX_REPORTS_PER_HOUR) return fail_('busy', 'Too many reports right now. Please try again later.');

    // Server-side validation (mirrors the form)
    const chain = String(d.supermarket || '');
    const address = String(d.address || '').trim();
    const photos = Array.isArray(d.photos) ? d.photos : [];
    if (CHAINS.indexOf(chain) < 0) return fail_('validation', 'Choose the supermarket.');
    if (address.length < 5 || address.length > 200) return fail_('validation', 'Enter the store address (street, postal code, city).');
    if (!photos.length) return fail_('validation', 'Add at least one photo of the price tag.');
    if (photos.length > MAX_FILES) return fail_('validation', 'Please send at most 10 photos at once.');

    const blobs = [];
    let total = 0;
    for (let k = 0; k < photos.length; k++) {
      const p = photos[k] || {};
      let bytes;
      try { bytes = Utilities.base64Decode(String(p.data || '')); } catch (err) { return fail_('validation', 'A photo could not be read.'); }
      const type = sniff_(bytes);  // trust the file content, not the declared type
      if (!type) return fail_('validation', 'Photos must be JPG or PNG images.');
      total += bytes.length;
      if (total > MAX_TOTAL_BYTES) return fail_('validation', 'The photos are larger than 10 MB in total.');
      const name = 'photo_' + (k + 1) + (type === 'image/png' ? '.png' : '.jpg');
      blobs.push(Utilities.newBlob(bytes, type, name));
    }

    // 1) Store privately in Drive (locked, so a simultaneous retry can't store the same report twice)
    const lock = LockService.getScriptLock();
    if (!lock.tryLock(20000)) return fail_('busy', 'The server is busy. Please try again.');
    try {
      if (cache.get('done:' + id)) return json_({ ok: true, duplicate: true });
      return store_(d, id, chain, address, blobs, cache, hourKey, n);
    } finally {
      lock.releaseLock();
    }
  } catch (err) {
    console.error(err);
    return fail_('server', 'The report could not be saved. Please try again.');
  }
}

function store_(d, id, chain, address, blobs, cache, hourKey, n) {
    const received = new Date();
    const stamp = Utilities.formatDate(received, 'Europe/Berlin', 'yyyy-MM-dd HH:mm:ss');
    const root = folder_();
    const sub = root.createFolder(stamp + ' ' + chain + ' ' + id.slice(0, 8));
    blobs.forEach(function (b) { sub.createFile(b); });
    const submittedAt = String(d.submittedAt || '').slice(0, 100);
    sub.createFile('report.txt',
      'Supermarket: ' + chain + '\nStore address: ' + address +
      '\nSubmitted at (visitor): ' + submittedAt + '\nReceived at (server): ' + stamp + ' (Munich time)' +
      '\nPhotos: ' + blobs.length + '\nReport id: ' + id + '\n', MimeType.PLAIN_TEXT);

    cache.put('done:' + id, '1', 21600);
    cache.put(hourKey, String(n + 1), 3600);

    // 2) Email the owner (the report is already safe in Drive if this fails)
    let emailed = true;
    try {
      MailApp.sendEmail({
        to: OWNER_EMAIL,
        subject: SUBJECT,
        body: 'Supermarket: ' + chain + '\nStore address: ' + address +
              '\nSubmitted at: ' + submittedAt + '\nReceived at: ' + stamp + ' (Munich time)' +
              '\nPhotos: ' + blobs.length + '\nDrive folder: ' + sub.getUrl() +
              '\n\nReview the photos before adding anything to data.json.',
        attachments: blobs
      });
    } catch (err) {
      emailed = false;
      console.error('Email failed for ' + id + ': ' + err);
    }
    return json_({ ok: true, emailed: emailed });
}

function sniff_(b) {
  if (b.length > 3 && (b[0] & 255) === 0xFF && (b[1] & 255) === 0xD8 && (b[2] & 255) === 0xFF) return 'image/jpeg';
  if (b.length > 8 && (b[0] & 255) === 0x89 && b[1] === 0x50 && b[2] === 0x4E && b[3] === 0x47) return 'image/png';
  return '';
}

function folder_() {
  const it = DriveApp.getFoldersByName(FOLDER_NAME);
  return it.hasNext() ? it.next() : DriveApp.createFolder(FOLDER_NAME);
}

function json_(o) {
  return ContentService.createTextOutput(JSON.stringify(o)).setMimeType(ContentService.MimeType.JSON);
}

function fail_(code, message) {
  return json_({ ok: false, error: code, message: message });
}
