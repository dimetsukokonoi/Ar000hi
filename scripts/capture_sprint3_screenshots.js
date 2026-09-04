const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

const OUTPUT_DIR = path.resolve(__dirname, '../Sprint-3');
if (!fs.existsSync(OUTPUT_DIR)) {
  fs.mkdirSync(OUTPUT_DIR, { recursive: true });
}

async function run() {
  const browser = await chromium.launch({
    executablePath: '/usr/bin/google-chrome',
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu']
  });

  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 2,
  });

  const page = await context.newPage();

  console.log('Logging in as Ayesha Rahman...');
  await page.goto('http://localhost:3000/login', { waitUntil: 'networkidle' });
  await page.fill('input[type="email"]', 'ayesha.rider@g.bracu.ac.bd');
  await page.fill('input[type="password"]', 'Password123!');
  await page.click('button[type="submit"]');
  await page.waitForTimeout(3000);

  // --- SCREENSHOT 1: Campus Pickup Hotspots (Interactive Map & Pins) ---
  console.log('Capturing 01_campus_pickup_hotspots.png from /dashboard...');
  await page.goto('http://localhost:3000/dashboard', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, '01_campus_pickup_hotspots.png'),
    fullPage: false
  });

  // Navigate to /dashboard/rides
  console.log('Navigating to /dashboard/rides...');
  await page.goto('http://localhost:3000/dashboard/rides', { waitUntil: 'networkidle' });
  await page.waitForTimeout(3000);

  // --- SCREENSHOT 6: Campus Rides Overview ---
  console.log('Capturing 06_campus_rides_overview.png...');
  await page.screenshot({
    path: path.join(OUTPUT_DIR, '06_campus_rides_overview.png'),
    fullPage: false
  });

  // --- SCREENSHOT 3: Female-Only Ride Mode ---
  console.log('Capturing 03_female_only_ride_mode.png...');
  const femaleBtn = page.locator('button:has-text("Female-Only")').first();
  if (await femaleBtn.count() > 0) {
    await femaleBtn.click();
    await page.waitForTimeout(800);
  }
  await page.evaluate(() => window.scrollBy(0, 200));
  await page.waitForTimeout(500);
  await page.screenshot({
    path: path.join(OUTPUT_DIR, '03_female_only_ride_mode.png'),
    fullPage: false
  });

  // --- SCREENSHOT 4: Multi-Stop Ride Support (Interactive Modal Breakdown) ---
  console.log('Capturing 04_multi_stop_ride_support.png...');
  await page.evaluate(() => window.scrollTo(0, 0));
  const allRidesBtn = page.locator('button:has-text("All Rides")').first();
  if (await allRidesBtn.count() > 0) {
    await allRidesBtn.click();
    await page.waitForTimeout(800);
  }
  // Click Request Seat button on the scheduled multi-stop ride
  const requestSeatBtn = page.locator('button:has-text("Request Seat")').first();
  if (await requestSeatBtn.count() > 0) {
    await requestSeatBtn.click();
    await page.waitForTimeout(1000);

    // Select custom intermediate pickup & dropoff in modal
    const modalSelects = page.locator('div[style*="position: fixed"] select');
    const modalCount = await modalSelects.count();
    if (modalCount >= 2) {
      await modalSelects.nth(0).selectOption({ index: 1 }); // Hatirjheel
      await modalSelects.nth(1).selectOption({ index: 2 }); // BRACU Main Academic Complex
      await page.waitForTimeout(600);
    }
  }
  await page.screenshot({
    path: path.join(OUTPUT_DIR, '04_multi_stop_ride_support.png'),
    fullPage: false
  });

  // Close modal
  const cancelBtn = page.locator('button:has-text("Cancel")').first();
  if (await cancelBtn.count() > 0) {
    await cancelBtn.click();
  } else {
    await page.keyboard.press('Escape');
  }
  await page.waitForTimeout(500);

  // --- SCREENSHOT 2: Campus Zone Smart Matching (with Match Results) ---
  console.log('Capturing 02_campus_zone_smart_matching.png...');
  await page.evaluate(() => window.scrollTo(0, 0));
  const smartMatchTab = page.locator('button:has-text("Smart Match")').first();
  if (await smartMatchTab.count() > 0) {
    await smartMatchTab.click();
    await page.waitForTimeout(1000);

    // Select pickup & dropoff by value
    const pickupSelect = page.locator('select.input.select').nth(0);
    const dropoffSelect = page.locator('select.input.select').nth(1);

    if (await pickupSelect.count() > 0) {
      await pickupSelect.selectOption('banasree');
    }
    if (await dropoffSelect.count() > 0) {
      await dropoffSelect.selectOption('gate 1');
    }

    // Click 08:00 AM Class quick preset
    const classPreset = page.locator('button:has-text("08:00 AM")').first();
    if (await classPreset.count() > 0) {
      await classPreset.click();
      await page.waitForTimeout(400);
    }

    // Click "Find Best Matches"
    const findBtn = page.locator('button:has-text("Find Best Matches")').first();
    if (await findBtn.count() > 0) {
      await findBtn.click();
      await page.waitForTimeout(2000);
    }
  }
  await page.screenshot({
    path: path.join(OUTPUT_DIR, '02_campus_zone_smart_matching.png'),
    fullPage: false
  });

  // --- SCREENSHOT 5: Scheduled Ride Booking (with Multi-stop & Schedule) ---
  console.log('Capturing 05_scheduled_ride_booking.png...');
  await page.evaluate(() => window.scrollTo(0, 0));
  const offerTab = page.locator('button:has-text("Offer Ride")').first();
  if (await offerTab.count() > 0) {
    await offerTab.click();
    await page.waitForTimeout(1000);

    // Select source & destination
    const offerPickup = page.locator('select.input.select').nth(0);
    const offerDropoff = page.locator('select.input.select').nth(1);
    if (await offerPickup.count() > 0) {
      await offerPickup.selectOption('mohakhali');
    }
    if (await offerDropoff.count() > 0) {
      await offerDropoff.selectOption('gate 1');
    }

    // Fare
    const fareInput = page.locator('input[type="number"]').first();
    if (await fareInput.count() > 0) {
      await fareInput.fill('85');
    }

    // Schedule datetime
    const dateInput = page.locator('input[type="datetime-local"]').first();
    if (await dateInput.count() > 0) {
      await dateInput.fill('2026-08-13T08:00');
    }

    // Add intermediate stops
    const addStopBtn = page.locator('button:has-text("+ Add Stop")').first();
    if (await addStopBtn.count() > 0) {
      await addStopBtn.click();
      await page.waitForTimeout(300);
      const stop1Select = page.locator('select.input.select').nth(2);
      if (await stop1Select.count() > 0) {
        await stop1Select.selectOption('rampura bridge');
      }

      await addStopBtn.click();
      await page.waitForTimeout(300);
      const stop2Select = page.locator('select.input.select').nth(3);
      if (await stop2Select.count() > 0) {
        await stop2Select.selectOption('aftabnagar');
      }
    }

    // Check female-only mode checkbox if present
    const femaleCheckbox = page.locator('input[type="checkbox"]').first();
    if (await femaleCheckbox.count() > 0) {
      await femaleCheckbox.check();
    }
  }
  await page.screenshot({
    path: path.join(OUTPUT_DIR, '05_scheduled_ride_booking.png'),
    fullPage: false
  });

  await browser.close();
  console.log('Successfully completed full visual capture suite for Sprint-3!');
}

run().catch(err => {
  console.error('Error during capture:', err);
  process.exit(1);
});
