import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
import time
import csv

keywords = [
    "data science"
]

driver = uc.Chrome(options=uc.ChromeOptions(), version_main=136)
driver.set_window_size(1300, 900)

jobs = []
job_seen_ids = set()

for keyword in keywords:
    print(f"\n🔎 Searching for: {keyword.upper()}")
    for page in range(0, 25):
        start = page * 20
        query = keyword.replace(" ", "+")
        url = f"https://www.foundit.in/search/entry-level-jobs?query={query}&experienceRanges=0~1&start={start}"
        print(f"📄 Page {page + 1} | URL: {url}")
        driver.get(url)
        time.sleep(5)

        job_cards = driver.find_elements(By.CSS_SELECTOR, "div.flex.flex-col.rounded-lg.bg-white.relative.w-auto.cursor-pointer")

        if not job_cards:
            print("⚠️ No job cards found. Moving to next keyword.")
            break

        for card in job_cards:
            try:
                title_elem = card.find_element(By.TAG_NAME, "h3")
                title = title_elem.text.strip()

                company_elem = card.find_element(By.XPATH, ".//span/p")
                company = company_elem.text.strip()

                # Extract salary, location, posted, tag
                salary = ""
                location = ""
                posted = ""
                tag = ""

                all_text = card.text.split("\n")
                for line in all_text:
                    line = line.strip()
                    if ("LPA" in line or "₹" in line) and not salary:
                        salary = line
                    elif any(loc in line for loc in ["India", "Remote", "Ahmedabad", "Hyderabad", "Bangalore"]) and not location:
                        location = line
                    elif "Posted" in line and not posted:
                        posted = line
                    elif "Apply" in line and not tag:
                        tag = line

                job_id = f"{title}-{company}-{location}-{posted}"
                if job_id not in job_seen_ids and title:
                    job_seen_ids.add(job_id)
                    jobs.append({
                        "Keyword": keyword,
                        "Title": title,
                        "Company": company,
                        "Location": location,
                        "Salary": salary,
                        "Tag": tag,
                        "Posted": posted
                    })

            except Exception as e:
                print(f"⚠️ Skipped a job card: {e}")

driver.quit()

if jobs:
    with open("foundit_all_tech_jobs_clean_1.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=jobs[0].keys())
        writer.writeheader()
        writer.writerows(jobs)
    print(f"\n✅ DONE: Saved {len(jobs)} jobs to foundit_all_tech_jobs_clean.csv")
else:
    print("❌ No jobs scraped.")
