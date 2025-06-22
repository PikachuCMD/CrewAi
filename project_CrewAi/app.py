from flask import Flask, request, render_template
from crewai import Crew, Agent, Task, LLM
import re
import os
import logging
import markdown2
from dotenv import load_dotenv

# โหลดค่าจาก .env
load_dotenv()

# ตั้งค่า logging (สำหรับเก็บ error log)
logging.basicConfig(filename='error.log', level=logging.ERROR)

app = Flask(__name__)

# ตรวจสอบและตั้งค่า API KEY
api_key = os.getenv('CREWAI_API_KEY')
if not api_key:
    raise ValueError("❌ ไม่พบค่า CREWAI_API_KEY ในไฟล์ .env กรุณาตั้งค่าก่อนเริ่มระบบ")

# ตั้งค่า LLM
llm = LLM(
    model='gemini/gemini-2.0-flash',
    api_key=api_key,
)

# สร้าง Agents
researcherAI = Agent(
    role="Researcher",
    goal="ค้นหาสถานที่ท่องเที่ยวที่ดีที่สุดในจังหวัดกำแพงเพชร",
    backstory="ผู้เชี่ยวชาญด้านการวิเคราะห์สถานที่ท่องเที่ยวในจังหวัดกำแพงเพชร",
    llm=llm
)

writerAI = Agent(
    role="Writer",
    goal="เขียนบทความท่องเที่ยวที่น่าสนใจเกี่ยวกับจังหวัดกำแพงเพชร",
    backstory="นักเขียนมืออาชีพที่เชี่ยวชาญในการเขียนแนะนำจังหวัดเดียว",
    llm=llm
)

reviewerAI = Agent(
    role="Reviewer",
    goal="เสริมบทความท่องเที่ยวจังหวัดกำแพงเพชรให้มีความน่าสนใจยิ่งขึ้น",
    backstory="นักท่องเที่ยวตัวยงที่วิจารณ์เชิงสร้างสรรค์",
    llm=llm
)

# ฟังก์ชันหลักสำหรับสร้างคำแนะนำ

def get_recommendations(age, gender, budget, language="thai"):
    try:
        research_task = Task(
            description=f"ค้นคว้าสถานที่ท่องเที่ยวในจังหวัดกำแพงเพชรที่เหมาะสมกับนักท่องเที่ยวเพศ {gender} อายุ {age} ปี งบประมาณ {budget} บาท โดยพิจารณาจากความปลอดภัย ความนิยม และกิจกรรมที่เหมาะกับช่วงวัย",
            expected_output=f"สรุปรายชื่อสถานที่แนะนำในจังหวัดกำแพงเพชรที่เหมาะกับเพศ {gender} อายุ {age} ปี และงบประมาณ {budget} บาท พร้อมคำอธิบาย",
            agent=researcherAI
        )

        writer_task = Task(
            description=f"เขียนบทความแนะนำการท่องเที่ยวจังหวัดกำแพงเพชรที่เหมาะกับผู้ที่มีอายุ {age} ปี เพศ {gender} และมีงบประมาณ {budget} บาท โดยให้รายละเอียดครบถ้วน",
            expected_output=f"""
กรุณาจัดรูปแบบผลลัพธ์เป็นหัวข้อดังนี้ (เป็นภาษาไทย):

1. **ภาพรวมจังหวัดกำแพงเพชร** (สั้น กระชับ)
2. **แผนการท่องเที่ยวที่แนะนำ** สำหรับผู้มีอายุ {age} เพศ {gender} พร้อมสถานที่ 3-5 แห่ง และกิจกรรมที่แนะนำในแต่ละที่
3. **คำนวณค่าใช้จ่ายโดยประมาณ** รวมทั้งกิน-อยู่-เดินทาง ภายในงบ {budget} บาท
4. **ข้อควรระวัง และเคล็ดลับ** ตามช่วงวัยและเพศ
5. **สรุปเหตุผลว่าทำไมแผนนี้เหมาะกับผู้ใช้**

ให้เขียนเป็น Markdown อย่างสวยงาม
""",
            agent=writerAI
        )

        reviews_task = Task(
            description=f"รีวิวแต่ละสถานที่ในจังหวัดกำแพงเพชรที่เลือกมา โดยประเมินตามความเหมาะสมกับเพศ {gender} อายุ {age} และงบ {budget} บาท",
            expected_output="รีวิวเชิงวิเคราะห์ข้อดีข้อเสียของแต่ละสถานที่ และคำแนะนำ",
            agent=reviewerAI
        )

        crew = Crew(agents=[researcherAI, writerAI, reviewerAI],
                    tasks=[research_task, writer_task, reviews_task])

        response = crew.kickoff(
            inputs={
                'topic': 'Tourism in Kamphaeng Phet',
                'language': language,
                'age': age,
                'gender': gender,
                'budget': budget
            }
        )
        return str(response)

    except Exception as e:
        logging.error(f"CrewAI error: {str(e)}")
        return f"❌ เกิดข้อผิดพลาด: {str(e)}"

# ฟังก์ชันดึงภาพ

def get_image_url(_):
    return "https://source.unsplash.com/600x400/?Kamphaeng-Phet,thailand"

# หน้าแรก (รับข้อมูล)

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        try:
            age = int(request.form.get("age", "").strip())
        except ValueError:
            return "กรุณากรอกอายุเป็นตัวเลข", 400

        gender = request.form.get("gender", "").strip()
        budget = request.form.get("budget", "").strip()
        language = request.form.get("language", "thai").strip()

        if not age or not gender or not budget:
            return "กรุณากรอกข้อมูลให้ครบทุกช่อง", 400

        result_raw = get_recommendations(age, gender, budget, language)
        result = markdown2.markdown(result_raw)
        image_url = get_image_url(result)

        return render_template("result.html", result=result, image_url=image_url)

    return render_template("user_form.html")

# สำรองหน้าแสดงผล

@app.route("/result", methods=["POST"])
def result_page():
    return render_template("result.html")

# เริ่มรัน Flask

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=os.getenv("FLASK_DEBUG", "False") == "True")
