import streamlit as st
import sqlite3
import time
import random
import pandas as pd
import threading
from datetime import datetime
import os

# --- Page Config ---
st.set_page_config(page_title="睡眠不足が脳機能に与える影響測定", layout="centered", initial_sidebar_state="expanded")

# --- Custom CSS for Mobile/Large Buttons ---
st.markdown("""
<style>
div.stButton > button:first-child {
    font-size: 1.2rem;
    height: 3em;
    width: 100%;
    margin-bottom: 10px;
}
</style>
""", unsafe_allow_html=True)

# --- Database Setup ---
DB_FILE = 'results.db'
db_lock = threading.Lock()

def init_db():
    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=10) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    student_id TEXT,
                    sleep_hours REAL,
                    total_score REAL,
                    reaction_score REAL,
                    calc_score REAL,
                    memory_score REAL,
                    nback_score REAL,
                    reaction_raw REAL,
                    calc_raw REAL,
                    memory_raw REAL,
                    nback_raw REAL
                )
            ''')
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(results)")
            columns = [col[1] for col in cursor.fetchall()]
            if 'sleep_hours' not in columns:
                conn.execute('ALTER TABLE results ADD COLUMN sleep_hours REAL')
            conn.commit()

init_db()

def save_result(data):
    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=10) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO results (
                    timestamp, student_id, sleep_hours, total_score, 
                    reaction_score, calc_score, memory_score, nback_score, 
                    reaction_raw, calc_raw, memory_raw, nback_raw
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', data)
            conn.commit()

def load_results():
    with db_lock:
        with sqlite3.connect(DB_FILE, timeout=10) as conn:
            df = pd.read_sql_query("SELECT * FROM results", conn)
            return df

# --- Sidebar Navigation ---
st.sidebar.title("メニュー")
pages = [
    "① 基本情報入力", 
    "② 反応速度テスト", 
    "③ 計算テスト", 
    "④ 画像記憶テスト", 
    "⑤ Nバック課題", 
    "⑥ 結果の送信", 
    "⑦ 教員用管理画面"
]
page = st.sidebar.radio("テスト一覧", pages)

# --- Check Basic Info ---
if page not in ["① 基本情報入力", "⑦ 教員用管理画面"]:
    if not st.session_state.get('student_id'):
        st.warning("⚠️ まずは「① 基本情報入力」から氏名または学籍番号を入力してください。")
        st.stop()

# ==========================================
# Page 1: 基本情報入力
# ==========================================
if page == "① 基本情報入力":
    st.header("① 基本情報入力")
    st.write("各テストの記録のため、基本情報を入力してください。")
    
    current_id = st.session_state.get('student_id', '')
    student_id = st.text_input("氏名または学籍番号", value=current_id)
    
    current_sleep = st.session_state.get('sleep_hours', 6.0)
    sleep_hours = st.number_input("昨晩の睡眠時間（時間）", min_value=0.0, max_value=24.0, value=current_sleep, step=0.5)
    
    if st.button("保存して進む", type="primary"):
        if student_id.strip() == "":
            st.error("氏名または学籍番号が空です。")
        else:
            st.session_state.student_id = student_id.strip()
            st.session_state.sleep_hours = sleep_hours
            st.success("保存しました！左のメニューから「② 反応速度テスト」に進んでください。")

# ==========================================
# Page 2: 反応速度テスト
# ==========================================
elif page == "② 反応速度テスト":
    st.header("② 反応速度テスト")
    st.write("ランダムな時間（2〜5秒）待機後、緑色のボタンが表示されます。できるだけ早くクリックしてください！")
    st.write("※ まずは1回練習を行います。本番は3回連続で行い、その平均がスコアになります。")
    
    if 'reaction_state' not in st.session_state:
        st.session_state.reaction_state = 'init'

    state = st.session_state.reaction_state

    # 練習スタート
    if state == 'init':
        if st.button("練習を開始", type="primary"):
            st.session_state.reaction_state = 'practice_waiting'
            st.session_state.wait_end = time.time() + random.uniform(2.0, 5.0)
            st.rerun()

    # 練習：待機中
    elif state == 'practice_waiting':
        if time.time() < st.session_state.wait_end:
            st.error("🔴 待機中... (まだ押さないでください)")
            if st.button("クリック", key="prac_flying"):
                st.warning("⚠️ フライングです！最初からやり直してください。")
                st.session_state.reaction_state = 'init'
                st.stop()
            time.sleep(0.1)
            st.rerun()
        else:
            st.session_state.reaction_state = 'practice_ready'
            st.session_state.reaction_start = time.time()
            st.rerun()

    # 練習：クリック
    elif state == 'practice_ready':
        st.success("🟢 今だ！クリック！")
        if st.button("ここをクリック！", key="prac_click", type="primary"):
            rt = (time.time() - st.session_state.reaction_start) * 1000
            st.session_state.prac_reaction_time = rt
            st.session_state.reaction_state = 'practice_done'
            st.rerun()

    # 練習：完了
    elif state == 'practice_done':
        st.info(f"【練習結果】 あなたの反応時間: {st.session_state.prac_reaction_time:.0f} ms")
        st.write("ルールは理解できましたか？次は本番（3回連続）です！")
        if st.button("本番を開始する", type="primary"):
            st.session_state.reaction_trials = []
            st.session_state.reaction_state = 'test_waiting'
            st.session_state.wait_end = time.time() + random.uniform(2.0, 5.0)
            st.rerun()

    # 本番：待機中
    elif state == 'test_waiting':
        trial_idx = len(st.session_state.reaction_trials) + 1
        st.write(f"### 本番: {trial_idx} 回目 / 3")
        
        if time.time() < st.session_state.wait_end:
            st.error("🔴 待機中... (まだ押さないでください)")
            if st.button("クリック", key=f"test_flying_{trial_idx}"):
                st.warning("⚠️ フライングです！この回をやり直します。")
                time.sleep(1.5)
                st.session_state.wait_end = time.time() + random.uniform(2.0, 5.0)
                st.rerun()
            time.sleep(0.1)
            st.rerun()
        else:
            st.session_state.reaction_state = 'test_ready'
            st.session_state.reaction_start = time.time()
            st.rerun()

    # 本番：クリック
    elif state == 'test_ready':
        trial_idx = len(st.session_state.reaction_trials) + 1
        st.write(f"### 本番: {trial_idx} 回目 / 3")
        st.success("🟢 今だ！クリック！")
        if st.button("ここをクリック！", key=f"test_click_{trial_idx}", type="primary"):
            rt = (time.time() - st.session_state.reaction_start) * 1000
            st.session_state.reaction_trials.append(rt)
            
            if len(st.session_state.reaction_trials) >= 3:
                st.session_state.reaction_state = 'test_done'
            else:
                st.session_state.reaction_state = 'test_waiting'
                st.session_state.wait_end = time.time() + random.uniform(2.0, 5.0)
            st.rerun()

    # 本番：完了
    elif state == 'test_done':
        trials = st.session_state.reaction_trials
        avg_rt = sum(trials) / len(trials)
        
        score = max(0, 100 - (avg_rt - 250) / 5)
        score = min(100, score)
        
        st.write("### すべての回が終了しました！")
        for i, rt in enumerate(trials):
            st.write(f"- {i+1}回目: {rt:.0f} ms")
        
        st.markdown(f"## **平均反応時間: {avg_rt:.0f} ms**")
        st.markdown(f"## **スコア: {score:.0f} / 100**")
        
        st.session_state.reaction_score = score
        st.session_state.reaction_time = avg_rt
        
        st.success("このテストは完了です。左のメニューから次のテストに進んでください。")

# ==========================================
# Page 3: 計算テスト
# ==========================================
elif page == "③ 計算テスト":
    st.header("③ 計算テスト")
    st.write("2桁と1桁の足し算・引き算を解いてください。")
    st.write("※ まずは練習（タイム計測なし）を2問行います。本番は10問正解するまでのタイムを計測します。")
    
    def generate_calc_q():
        op = random.choice(['+', '-'])
        a = random.randint(10, 99)
        b = random.randint(1, 9)
        if op == '+':
            return f"{a} ＋ {b} ＝ ?", a + b
        else:
            return f"{a} － {b} ＝ ?", a - b

    if 'calc_state' not in st.session_state:
        st.session_state.calc_state = 'init'

    state = st.session_state.calc_state

    # 練習スタート
    if state == 'init':
        if st.button("練習を開始", type="primary"):
            st.session_state.calc_state = 'practice_playing'
            st.session_state.calc_correct = 0
            st.session_state.calc_q, st.session_state.calc_ans = generate_calc_q()
            st.rerun()

    # 練習：プレイ中
    elif state == 'practice_playing':
        st.write(f"### 【練習】 問題 {st.session_state.calc_correct + 1} / 2")
        st.header(st.session_state.calc_q)
        
        with st.form("calc_prac_form", clear_on_submit=True):
            user_ans = st.text_input("答えを半角数字で入力してください")
            submitted = st.form_submit_button("回答")
            
            if submitted:
                try:
                    if int(user_ans) == st.session_state.calc_ans:
                        st.session_state.calc_correct += 1
                        if st.session_state.calc_correct >= 2:
                            st.session_state.calc_state = 'practice_done'
                        else:
                            st.session_state.calc_q, st.session_state.calc_ans = generate_calc_q()
                        st.rerun()
                    else:
                        st.error("間違いです！もう一度！")
                except ValueError:
                    st.error("数字を入力してください。")

    # 練習：完了
    elif state == 'practice_done':
        st.info("練習が完了しました。やり方は理解できましたか？")
        st.write("本番は **10問** です。タイムが計測されるので、できるだけ早く正確に答えてください！")
        if st.button("本番を開始する", type="primary"):
            st.session_state.calc_state = 'test_playing'
            st.session_state.calc_correct = 0
            st.session_state.calc_start = time.time()
            st.session_state.calc_q, st.session_state.calc_ans = generate_calc_q()
            st.rerun()

    # 本番：プレイ中
    elif state == 'test_playing':
        st.write(f"### 【本番】 問題 {st.session_state.calc_correct + 1} / 10")
        st.header(st.session_state.calc_q)
        
        with st.form("calc_test_form", clear_on_submit=True):
            user_ans = st.text_input("答えを半角数字で入力してください")
            submitted = st.form_submit_button("回答")
            
            if submitted:
                try:
                    if int(user_ans) == st.session_state.calc_ans:
                        st.session_state.calc_correct += 1
                        if st.session_state.calc_correct >= 10:
                            st.session_state.calc_time = time.time() - st.session_state.calc_start
                            st.session_state.calc_state = 'test_done'
                        else:
                            st.session_state.calc_q, st.session_state.calc_ans = generate_calc_q()
                        st.rerun()
                    else:
                        st.error("間違いです！もう一度！")
                except ValueError:
                    st.error("数字を入力してください。")

    # 本番：完了
    elif state == 'test_done':
        calc_time = st.session_state.calc_time
        score = max(0, 100 - (calc_time - 15) * 2)
        score = min(100, score)
        
        st.write(f"### クリアタイム: {calc_time:.1f} 秒")
        st.write(f"### スコア: {score:.0f} / 100")
        
        st.session_state.calc_score = score
        st.session_state.calc_raw = calc_time
        
        st.success("このテストは完了です。左のメニューから次のテストに進んでください。")


# ==========================================
# Page 4: 画像記憶テスト
# ==========================================
elif page == "④ 画像記憶テスト":
    st.header("④ 画像記憶テスト")
    st.write("3×3のマスに異なる絵文字が9つ表示されます。配置を記憶してください！")
    st.write("※ まずは練習です。10秒間表示された後、2問出題されます。本番は20秒表示され、5問出題されます。")
    
    ALL_EMOJIS = ["🍎", "🐶", "🚗", "⚽", "🎸", "🌞", "📱", "📚", "🍕", "🐱", "🚀", "🌸", "🎈", "🍔", "🚲", "🍉", "🐘", "⏰", "🍦", "🎹"]
    
    if 'img_state' not in st.session_state:
        st.session_state.img_state = 'init'

    state = st.session_state.img_state

    # 練習スタート
    if state == 'init':
        if st.button("練習を開始", type="primary"):
            st.session_state.img_state = 'practice_memorize'
            st.session_state.img_grid = random.sample(ALL_EMOJIS, 9)
            st.session_state.img_start = time.time()
            st.rerun()

    # 練習：記憶
    elif state == 'practice_memorize':
        st.info("【練習】10秒間、以下の配置を記憶してください！")
        grid = st.session_state.img_grid
        for r in range(3):
            cols = st.columns(3)
            for c in range(3):
                cols[c].markdown(f"<h1 style='text-align: center;'>{grid[r*3+c]}</h1>", unsafe_allow_html=True)
        
        if time.time() - st.session_state.img_start > 10.0:
            st.session_state.img_state = 'practice_question'
            st.session_state.img_q_idx = 0
            st.session_state.img_correct = 0
            st.session_state.img_qs = random.sample(grid, 2)
            st.rerun()
        else:
            time.sleep(0.5)
            st.rerun()

    # 練習：クイズ
    elif state == 'practice_question':
        q_idx = st.session_state.img_q_idx
        if q_idx < 2:
            target = st.session_state.img_qs[q_idx]
            st.write(f"### 【練習】 第 {q_idx+1} 問")
            st.markdown(f"<h2 style='text-align: center;'>「 {target} 」 はどこにありましたか？</h2>", unsafe_allow_html=True)
            
            options = ["上段・左", "上段・中", "上段・右", "中段・左", "中段・中", "中段・右", "下段・左", "下段・中", "下段・右"]
            ans_idx = st.session_state.img_grid.index(target)
            correct_opt = options[ans_idx]
            
            user_choice = st.radio("場所を選択してください", options, index=None, key=f"prac_img_q_{q_idx}")
            if st.button("回答する", type="primary"):
                if user_choice == correct_opt:
                    st.session_state.img_correct += 1
                    st.success("正解！")
                else:
                    st.error(f"不正解... 正解は「{correct_opt}」でした。")
                time.sleep(1.5)
                st.session_state.img_q_idx += 1
                st.rerun()
        else:
            st.session_state.img_state = 'practice_done'
            st.rerun()

    # 練習：完了
    elif state == 'practice_done':
        correct = st.session_state.img_correct
        st.info(f"【練習結果】 正解数: {correct} / 2")
        st.write("本番は **20秒間** 記憶する時間が与えられ、問題は **5問** になります！")
        if st.button("本番を開始する", type="primary"):
            st.session_state.img_state = 'test_memorize'
            st.session_state.img_grid = random.sample(ALL_EMOJIS, 9)
            st.session_state.img_start = time.time()
            st.rerun()

    # 本番：記憶
    elif state == 'test_memorize':
        st.info("【本番】20秒間、以下の配置を記憶してください！")
        grid = st.session_state.img_grid
        for r in range(3):
            cols = st.columns(3)
            for c in range(3):
                cols[c].markdown(f"<h1 style='text-align: center;'>{grid[r*3+c]}</h1>", unsafe_allow_html=True)
        
        if time.time() - st.session_state.img_start > 20.0:
            st.session_state.img_state = 'test_question'
            st.session_state.img_q_idx = 0
            st.session_state.img_correct = 0
            st.session_state.img_qs = random.sample(grid, 5)
            st.rerun()
        else:
            time.sleep(0.5)
            st.rerun()

    # 本番：クイズ
    elif state == 'test_question':
        q_idx = st.session_state.img_q_idx
        if q_idx < 5:
            target = st.session_state.img_qs[q_idx]
            st.write(f"### 【本番】 第 {q_idx+1} 問")
            st.markdown(f"<h2 style='text-align: center;'>「 {target} 」 はどこにありましたか？</h2>", unsafe_allow_html=True)
            
            options = ["上段・左", "上段・中", "上段・右", "中段・左", "中段・中", "中段・右", "下段・左", "下段・中", "下段・右"]
            ans_idx = st.session_state.img_grid.index(target)
            correct_opt = options[ans_idx]
            
            user_choice = st.radio("場所を選択してください", options, index=None, key=f"test_img_q_{q_idx}")
            if st.button("回答する", type="primary"):
                if user_choice == correct_opt:
                    st.session_state.img_correct += 1
                st.session_state.img_q_idx += 1
                st.rerun()
        else:
            st.session_state.img_state = 'test_done'
            st.rerun()

    # 本番：完了
    elif state == 'test_done':
        correct = st.session_state.img_correct
        score = (correct / 5.0) * 100
        
        st.write(f"### 正解数: {correct} / 5")
        st.write(f"### スコア: {score:.0f} / 100")
        
        st.session_state.memory_score = score
        st.session_state.memory_raw = correct
        
        st.success("このテストは完了です。左のメニューから次のテストに進んでください。")

# ==========================================
# Page 5: Nバック課題
# ==========================================
elif page == "⑤ Nバック課題":
    st.header("⑤ Nバック課題")
    
    # 詳しいルール説明
    st.markdown("""
    ### 📝 ルール説明
    画面中央のアルファベットが **1.5秒間隔** で次々と切り替わります。
    現在表示されている文字が **「2つ前の文字」と同じ場合** だけ、素早く「👆 2つ前と同じ！」ボタンを押してください。
    
    **【例：文字の出方とボタンを押すタイミング】**
    1. `A` （何もしない）
    2. `B` （何もしない）
    3. `A` ➔ **2つ前（1番目）と同じなのでボタンを押す！**
    4. `C` （何もしない）
    5. `D` （何もしない）
    6. `D` （1つ前と同じだが、**2つ前ではない**ので押さない）
    """)
    st.write("※ まずは短めの練習（10回切り替え）を行い、その後本番（15回切り替え）を行います。")
    
    def generate_nback_sequence(length=15, n=2, match_prob=0.35):
        letters = "ABCDEF"
        seq = []
        for i in range(length):
            if i >= n and random.random() < match_prob:
                seq.append(seq[i-n])
            else:
                choices = list(letters)
                if i >= n and seq[i-n] in choices:
                    choices.remove(seq[i-n])
                seq.append(random.choice(choices))
        return seq

    if 'nback_state' not in st.session_state:
        st.session_state.nback_state = 'init'

    state = st.session_state.nback_state

    # 練習スタート
    if state == 'init':
        if st.button("練習を開始", type="primary"):
            st.session_state.nback_state = 'practice_playing'
            st.session_state.nback_seq = generate_nback_sequence(length=10)
            st.session_state.nback_idx = 0
            st.session_state.nback_answers = {}
            st.session_state.nback_step_start = time.time()
            st.rerun()

    # 練習：プレイ中
    elif state == 'practice_playing':
        idx = st.session_state.nback_idx
        if idx >= 10:
            st.session_state.nback_state = 'practice_done'
            st.rerun()
            
        st.write(f"### 【練習】 進行状況: {idx + 1} / 10")
        
        elapsed = time.time() - st.session_state.nback_step_start
        if elapsed < 1.0:
            st.markdown(f"<h1 style='text-align: center; font-size: 5rem;'>{st.session_state.nback_seq[idx]}</h1>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h1 style='text-align: center; font-size: 5rem; color: #888;'>＋</h1>", unsafe_allow_html=True)
        
        match_clicked = st.button("👆 2つ前と同じ！", key=f"prac_nback_btn_{idx}", type="primary")
        if match_clicked:
            st.session_state.nback_answers[idx] = True
            st.success("入力を受け付けました！")
        
        if elapsed >= 1.5:
            st.session_state.nback_idx += 1
            st.session_state.nback_step_start = time.time()
            st.rerun()
        else:
            time.sleep(0.1)
            st.rerun()

    # 練習：完了
    elif state == 'practice_done':
        seq = st.session_state.nback_seq
        answers = st.session_state.nback_answers
        correct_count = sum([1 for i in range(2, 10) if (seq[i] == seq[i-2]) == answers.get(i, False)])
        total_targets = 8
        
        st.info(f"【練習結果】 正解数: {correct_count} / {total_targets}")
        st.write("ルールは掴めましたか？本番は **15回** 切り替わります。集中して取り組んでください！")
        
        if st.button("本番を開始する", type="primary"):
            st.session_state.nback_state = 'test_playing'
            st.session_state.nback_seq = generate_nback_sequence(length=15)
            st.session_state.nback_idx = 0
            st.session_state.nback_answers = {}
            st.session_state.nback_step_start = time.time()
            st.rerun()

    # 本番：プレイ中
    elif state == 'test_playing':
        idx = st.session_state.nback_idx
        if idx >= 15:
            st.session_state.nback_state = 'test_done'
            st.rerun()
            
        st.write(f"### 【本番】 進行状況: {idx + 1} / 15")
        
        elapsed = time.time() - st.session_state.nback_step_start
        if elapsed < 1.0:
            st.markdown(f"<h1 style='text-align: center; font-size: 5rem;'>{st.session_state.nback_seq[idx]}</h1>", unsafe_allow_html=True)
        else:
            st.markdown(f"<h1 style='text-align: center; font-size: 5rem; color: #888;'>＋</h1>", unsafe_allow_html=True)
        
        match_clicked = st.button("👆 2つ前と同じ！", key=f"test_nback_btn_{idx}", type="primary")
        if match_clicked:
            st.session_state.nback_answers[idx] = True
            st.success("入力を受け付けました！")
        
        if elapsed >= 1.5:
            st.session_state.nback_idx += 1
            st.session_state.nback_step_start = time.time()
            st.rerun()
        else:
            time.sleep(0.1)
            st.rerun()

    # 本番：完了
    elif state == 'test_done':
        seq = st.session_state.nback_seq
        answers = st.session_state.nback_answers
        
        correct_count = 0
        total_targets = 13 # index 2 to 14
        
        for i in range(2, 15):
            is_match = (seq[i] == seq[i-2])
            user_pressed = answers.get(i, False)
            if is_match == user_pressed:
                correct_count += 1
                
        score = (correct_count / total_targets) * 100
        
        st.write("### テスト終了！")
        st.write(f"### 正解率: {correct_count} / {total_targets}")
        st.write(f"### スコア: {score:.0f} / 100")
        
        st.session_state.nback_score = score
        st.session_state.nback_raw = correct_count
        
        st.success("このテストは完了です。左のメニューから次のテストに進んでください。")

# ==========================================
# Page 6: 結果の送信
# ==========================================
elif page == "⑥ 結果の送信":
    st.header("⑥ 結果の送信")
    
    required_scores = ['reaction_score', 'calc_score', 'memory_score', 'nback_score']
    missing = []
    if 'reaction_score' not in st.session_state: missing.append("② 反応速度テスト")
    if 'calc_score' not in st.session_state: missing.append("③ 計算テスト")
    if 'memory_score' not in st.session_state: missing.append("④ 画像記憶テスト")
    if 'nback_score' not in st.session_state: missing.append("⑤ Nバック課題")
    
    if missing:
        st.warning("まだ完了していないテストがあります。すべてのテストを完了してから送信してください。")
        for m in missing:
            st.write(f"- {m}")
    else:
        reaction = st.session_state.reaction_score
        calc = st.session_state.calc_score
        memory = st.session_state.memory_score
        nback = st.session_state.nback_score
        total = (reaction + calc + memory + nback) / 4
        
        st.success("すべてのテストが完了しています！")
        st.write("### あなたの結果")
        st.write(f"- **反応速度スコア**: {reaction:.0f}")
        st.write(f"- **計算テストスコア**: {calc:.0f}")
        st.write(f"- **画像記憶スコア**: {memory:.0f}")
        st.write(f"- **Nバックスコア**: {nback:.0f}")
        st.markdown(f"## **総合スコア**: {total:.1f} / 100")
        
        if st.button("結果をサーバーに送信する", type="primary"):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            student_id = st.session_state.student_id
            sleep_hours = st.session_state.get('sleep_hours', 0.0)
            
            data = (
                timestamp, student_id, sleep_hours, total,
                reaction, calc, memory, nback,
                st.session_state.reaction_time,
                st.session_state.calc_raw,
                st.session_state.memory_raw,
                st.session_state.nback_raw
            )
            
            save_result(data)
            st.success("✅ 送信完了しました！ご協力ありがとうございました。")
            st.balloons()

# ==========================================
# Page 7: 教員用管理画面
# ==========================================
elif page == "⑦ 教員用管理画面":
    st.header("⑦ 教員用管理画面 (Teacher Admin)")
    
    if 'admin_auth' not in st.session_state:
        st.session_state.admin_auth = False
        
    if not st.session_state.admin_auth:
        pwd = st.text_input("パスワードを入力してください", type="password")
        if st.button("ログイン"):
            if pwd == "admin123":
                st.session_state.admin_auth = True
                st.rerun()
            else:
                st.error("パスワードが違います")
    else:
        st.success("ログイン成功")
        
        df = load_results()
        if df.empty:
            st.info("まだデータがありません。")
        else:
            st.write(f"総データ件数: {len(df)}件")
            st.dataframe(df)
            
            csv = df.to_csv(index=False).encode('utf-8-sig')
            st.download_button(
                label="一括ダウンロード (CSV)",
                data=csv,
                file_name="sleep_test_results.csv",
                mime="text/csv",
            )
            
        if st.button("ログアウト"):
            st.session_state.admin_auth = False
            st.rerun()
