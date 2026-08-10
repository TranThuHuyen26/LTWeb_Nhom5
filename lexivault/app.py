from flask import Flask, render_template, jsonify, request, session, redirect, url_for, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3, os, json, csv, io, math, functools, random, re, base64, wave
from datetime import datetime, date

app = Flask(__name__)
app.secret_key = 'lexivault_pro_secret_2024'
DB = os.path.join(os.path.dirname(__file__), 'lexivault.db')


def load_env_file():
    env_path = os.path.join(os.path.dirname(__file__), '.env')
    if not os.path.exists(env_path):
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


load_env_file()

LANG_MAP = {'en': '🇬🇧 Tiếng Anh', 'ja': '🇯🇵 Tiếng Nhật', 'ko': '🇰🇷 Tiếng Hàn', 'fr': '🇫🇷 Tiếng Pháp', 'vi': '🇻🇳 Tiếng Việt'}
LEVEL_MAP = {'beginner': 'Cơ bản', 'intermediate': 'Trung cấp', 'advanced': 'Nâng cao'}
GRADIENT_MAP = {
    'en': ('135deg', '#2ECC71', '#16A085'),
    'ja': ('135deg', '#E74C3C', '#8E44AD'),
    'ko': ('135deg', '#3498DB', '#1ABC9C'),
    'fr': ('135deg', '#F39C12', '#E74C3C'),
}


def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        email TEXT,
        role TEXT DEFAULT 'user',
        is_active INTEGER DEFAULT 1,
        xp INTEGER DEFAULT 0,
        gems INTEGER DEFAULT 100,
        streak INTEGER DEFAULT 0,
        max_streak INTEGER DEFAULT 0,
        last_study DATE,
        avatar TEXT DEFAULT '🧑',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS decks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        language TEXT DEFAULT 'en',
        level TEXT DEFAULT 'beginner',
        category TEXT DEFAULT 'general',
        emoji TEXT DEFAULT '📚',
        color TEXT DEFAULT '#2ECC71',
        is_public INTEGER DEFAULT 1,
        download_count INTEGER DEFAULT 0,
        word_count INTEGER DEFAULT 0,
        created_by INTEGER,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS words (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        deck_id INTEGER NOT NULL,
        word TEXT NOT NULL,
        pronunciation TEXT,
        meaning TEXT NOT NULL,
        meaning_en TEXT,
        example TEXT,
        example_vn TEXT,
        part_of_speech TEXT DEFAULT 'word',
        synonyms TEXT,
        order_idx INTEGER DEFAULT 0,
        FOREIGN KEY(deck_id) REFERENCES decks(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS user_decks (
        user_id INTEGER NOT NULL,
        deck_id INTEGER NOT NULL,
        added_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, deck_id)
    );
    CREATE TABLE IF NOT EXISTS study_progress (
        user_id INTEGER NOT NULL,
        word_id INTEGER NOT NULL,
        deck_id INTEGER NOT NULL,
        status TEXT DEFAULT 'new',
        correct_count INTEGER DEFAULT 0,
        wrong_count INTEGER DEFAULT 0,
        ease_factor REAL DEFAULT 2.5,
        sr_interval INTEGER DEFAULT 0,
        repetitions INTEGER DEFAULT 0,
        next_review DATETIME,
        last_studied DATETIME,
        UNIQUE(user_id, word_id)
    );
    CREATE TABLE IF NOT EXISTS game_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        deck_id INTEGER,
        game TEXT NOT NULL,
        score INTEGER DEFAULT 0,
        duration_sec INTEGER DEFAULT 0,
        xp_earned INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    -- REPLACED BELOW
    CREATE TABLE IF NOT EXISTS _skip_achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        achievement TEXT NOT NULL,
        earned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, achievement)
    );

    CREATE TABLE IF NOT EXISTS daily_challenges (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT UNIQUE NOT NULL,
        deck_id INTEGER,
        word_id INTEGER,
        challenge_type TEXT DEFAULT 'quiz',
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    );
    CREATE TABLE IF NOT EXISTS daily_challenge_completions (
        user_id INTEGER NOT NULL,
        challenge_id INTEGER NOT NULL,
        score INTEGER DEFAULT 0,
        xp_earned INTEGER DEFAULT 0,
        completed_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY(user_id, challenge_id)
    );
    CREATE TABLE IF NOT EXISTS achievements (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        code TEXT NOT NULL,
        name TEXT NOT NULL,
        description TEXT,
        icon TEXT DEFAULT '🏆',
        earned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, code)
    );
    CREATE TABLE IF NOT EXISTS study_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        words_studied INTEGER DEFAULT 0,
        xp_earned INTEGER DEFAULT 0,
        UNIQUE(user_id, date)
    );
    ''')

    conn.commit()

    # Seed users
    try:
        c.execute("INSERT INTO users(username,password,role,xp,streak,gems,avatar) VALUES(?,?,?,?,?,?,?)",
                  ('admin', generate_password_hash('admin123'), 'admin', 2500, 15, 999, '👑'))
        c.execute("INSERT INTO users(username,password,xp,streak,gems,avatar) VALUES(?,?,?,?,?,?)",
                  ('demo', generate_password_hash('demo123'), 850, 5, 200, '🎓'))
        c.execute("INSERT INTO users(username,password,xp,streak,gems,avatar) VALUES(?,?,?,?,?,?)",
                  ('alice', generate_password_hash('alice123'), 1200, 8, 350, '🌟'))
    except:
        pass

    _seed_decks(c)
    conn.commit()
    conn.close()


def _seed_decks(c):
    decks = [
        (1, 'IELTS Academic', 'Từ vựng học thuật cho kỳ thi IELTS 6.5-8.0', 'en', 'advanced', 'ielts', '🎓', '#8E44AD'),
        (2, 'TOEIC 600+', 'Bộ từ vựng thiết yếu cho TOEIC đạt 600-990 điểm', 'en', 'intermediate', 'toeic', '📊',
         '#2980B9'),
        (3, 'TOEFL iBT', 'Từ vựng nâng cao cho kỳ thi TOEFL iBT', 'en', 'advanced', 'toefl', '🏛️', '#16A085'),
        (4, 'Business English', 'Tiếng Anh thương mại & văn phòng chuyên nghiệp', 'en', 'intermediate', 'business', '💼',
         '#E67E22'),
        (5, 'Daily Conversation', 'Từ vựng giao tiếp hàng ngày tự nhiên & thực dụng', 'en', 'beginner', 'daily', '💬',
         '#27AE60'),
        (6, 'Academic Writing', 'Từ nối & cụm từ học thuật cho essay & báo cáo', 'en', 'advanced', 'academic', '✍️',
         '#2C3E50'),
        (7, 'Travel & Culture', 'Từ vựng du lịch & văn hóa quốc tế', 'en', 'beginner', 'travel', '✈️', '#E74C3C'),
        (8, 'Technology & IT', 'Từ vựng công nghệ, lập trình & khởi nghiệp', 'en', 'intermediate', 'tech', '💻',
         '#1ABC9C'),
        (9, '日本語 N5-N4', 'Từ vựng tiếng Nhật cơ bản đến trung cấp', 'ja', 'beginner', 'japanese', '🗾', '#E74C3C'),
        (10, '한국어 TOPIK I-II', 'Từ vựng tiếng Hàn cho kỳ thi TOPIK', 'ko', 'beginner', 'korean', '🇰🇷', '#3498DB'),
    ]
    for d in decks:
        try:
            c.execute(
                "INSERT INTO decks(id,name,description,language,level,category,emoji,color) VALUES(?,?,?,?,?,?,?,?)", d)
        except:
            pass

    all_words = {
        1: [  # IELTS
            ('abundant', 'əˈbʌndənt', 'dồi dào, phong phú', 'adj', 'Natural resources are abundant in this region.',
             'Tài nguyên thiên nhiên dồi dào ở vùng này.', 'plentiful, ample'),
            ('ambiguous', 'æmˈbɪɡjuəs', 'mơ hồ, không rõ ràng', 'adj', 'The law is ambiguous on this issue.',
             'Luật pháp không rõ ràng về vấn đề này.', 'unclear, vague'),
            ('coherent', 'koʊˈhɪərənt', 'mạch lạc, nhất quán', 'adj', 'Please present a coherent argument.',
             'Hãy trình bày một lập luận mạch lạc.', 'logical, consistent'),
            ('controversial', 'ˌkɒntrəˈvɜːʃəl', 'gây tranh cãi', 'adj', 'Climate change remains a controversial topic.',
             'Biến đổi khí hậu vẫn là chủ đề gây tranh cãi.', 'disputed, debatable'),
            ('deteriorate', 'dɪˈtɪəriəreɪt', 'xấu đi, suy thoái', 'v',
             'The patient\'s condition deteriorated overnight.', 'Tình trạng bệnh nhân xấu đi qua đêm.',
             'worsen, decline'),
            ('elaborate', 'ɪˈlæbərət', 'chi tiết, phức tạp', 'adj', 'He gave an elaborate explanation.',
             'Anh ấy đưa ra một giải thích chi tiết.', 'detailed, complex'),
            ('fluctuate', 'ˈflʌktʃueɪt', 'dao động, biến động', 'v', 'Prices fluctuate with demand.',
             'Giá cả dao động theo nhu cầu.', 'vary, oscillate'),
            ('hypothetical', 'ˌhaɪpəˈθetɪkəl', 'giả thuyết, giả định', 'adj',
             'Let\'s consider a hypothetical scenario.', 'Hãy xem xét một kịch bản giả định.',
             'theoretical, speculative'),
            ('inevitable', 'ɪnˈevɪtəbl', 'không thể tránh khỏi', 'adj', 'Change is inevitable in any organization.',
             'Sự thay đổi là không thể tránh khỏi trong bất kỳ tổ chức nào.', 'unavoidable, certain'),
            ('mitigate', 'ˈmɪtɪɡeɪt', 'giảm nhẹ, làm dịu', 'v', 'We must mitigate the effects of pollution.',
             'Chúng ta phải giảm nhẹ tác động của ô nhiễm.', 'reduce, alleviate'),
            ('paradigm', 'ˈpærədaɪm', 'mô hình, hệ tư tưởng', 'n', 'This discovery shifted the scientific paradigm.',
             'Khám phá này đã thay đổi mô hình khoa học.', 'model, framework'),
            ('substantial', 'səbˈstænʃəl', 'đáng kể, quan trọng', 'adj', 'There has been substantial progress.',
             'Đã có sự tiến bộ đáng kể.', 'significant, considerable'),
            ('sustainable', 'səˈsteɪnəbl', 'bền vững', 'adj', 'We need sustainable development.',
             'Chúng ta cần phát triển bền vững.', 'viable, long-term'),
            ('unprecedented', 'ʌnˈpresɪdentɪd', 'chưa từng có tiền lệ', 'adj',
             'The pandemic caused unprecedented disruption.', 'Đại dịch gây ra sự gián đoạn chưa từng có.',
             'unparalleled, novel'),
            ('vulnerable', 'ˈvʌlnərəbl', 'dễ bị tổn thương', 'adj', 'Children are particularly vulnerable.',
             'Trẻ em đặc biệt dễ bị tổn thương.', 'susceptible, at risk'),
        ],
        2: [  # TOEIC
            ('accomplish', 'əˈkɒmplɪʃ', 'hoàn thành, đạt được', 'v', 'We accomplished all our targets.',
             'Chúng tôi đã hoàn thành tất cả mục tiêu.', 'achieve, complete'),
            ('allocate', 'ˈæləkeɪt', 'phân bổ, phân phối', 'v', 'Resources must be allocated wisely.',
             'Tài nguyên phải được phân bổ một cách khôn ngoan.', 'assign, distribute'),
            ('delegate', 'ˈdelɪɡeɪt', 'ủy quyền, giao phó', 'v', 'Learn to delegate tasks effectively.',
             'Học cách ủy quyền nhiệm vụ hiệu quả.', 'assign, entrust'),
            ('discrepancy', 'dɪˈskrepənsi', 'sự mâu thuẫn, bất nhất', 'n', 'There is a discrepancy in the report.',
             'Có sự mâu thuẫn trong báo cáo.', 'inconsistency, difference'),
            ('expenditure', 'ɪkˈspendɪtʃər', 'chi tiêu, chi phí', 'n', 'Keep track of all expenditures.',
             'Theo dõi tất cả các khoản chi tiêu.', 'spending, expense'),
            ('fiscal', 'ˈfɪskəl', 'thuộc tài chính, ngân sách', 'adj', 'The fiscal year ends in December.',
             'Năm tài chính kết thúc vào tháng 12.', 'financial, monetary'),
            ('inventory', 'ˈɪnvəntri', 'hàng tồn kho, kiểm kê', 'n', 'Check the inventory before ordering.',
             'Kiểm tra hàng tồn kho trước khi đặt hàng.', 'stock, supply'),
            ('liability', 'ˌlaɪəˈbɪlɪti', 'trách nhiệm pháp lý, nợ', 'n', 'The company has significant liabilities.',
             'Công ty có khoản nợ đáng kể.', 'debt, obligation'),
            ('lucrative', 'ˈluːkrətɪv', 'sinh lợi, có lãi', 'adj', 'This is a lucrative business opportunity.',
             'Đây là cơ hội kinh doanh sinh lợi.', 'profitable, rewarding'),
            ('mandatory', 'ˈmændətɔːri', 'bắt buộc, cưỡng bức', 'adj', 'Attendance is mandatory for all employees.',
             'Việc tham dự là bắt buộc đối với tất cả nhân viên.', 'compulsory, required'),
            ('negotiate', 'nɪˈɡoʊʃieɪt', 'đàm phán, thương lượng', 'v', 'They negotiated a better contract.',
             'Họ đã đàm phán một hợp đồng tốt hơn.', 'bargain, discuss'),
            ('procurement', 'prəˈkjʊərmənt', 'mua sắm, thu mua', 'n', 'The procurement process was streamlined.',
             'Quy trình mua sắm đã được đơn giản hóa.', 'purchasing, acquisition'),
            ('quarterly', 'ˈkwɔːtərli', 'theo quý, hàng quý', 'adj', 'We review targets on a quarterly basis.',
             'Chúng tôi xem xét mục tiêu theo quý.', 'every three months'),
            ('streamline', 'ˈstriːmlaɪn', 'đơn giản hóa, tối ưu hóa', 'v', 'We need to streamline our operations.',
             'Chúng tôi cần tối ưu hóa hoạt động.', 'simplify, optimize'),
            ('workforce', 'ˈwɜːrkfɔːrs', 'lực lượng lao động', 'n', 'The workforce needs better training.',
             'Lực lượng lao động cần được đào tạo tốt hơn.', 'employees, staff'),
        ],
        3: [  # TOEFL
            ('accommodate', 'əˈkɒmədeɪt', 'đáp ứng, chứa đựng', 'v', 'The hall can accommodate 500 people.',
             'Hội trường có thể chứa 500 người.', 'hold, contain'),
            ('aggregate', 'ˈæɡrɪɡət', 'tổng hợp, tích lũy', 'v', 'Data was aggregated from multiple sources.',
             'Dữ liệu được tổng hợp từ nhiều nguồn.', 'combine, collect'),
            ('catalyst', 'ˈkætəlɪst', 'chất xúc tác, nhân tố thúc đẩy', 'n', 'Education is a catalyst for change.',
             'Giáo dục là chất xúc tác cho sự thay đổi.', 'trigger, stimulus'),
            ('deduce', 'dɪˈdjuːs', 'suy luận, rút ra kết luận', 'v', 'We can deduce the answer from context.',
             'Chúng ta có thể suy luận câu trả lời từ ngữ cảnh.', 'infer, conclude'),
            ('empirical', 'ɪmˈpɪrɪkəl', 'dựa trên thực nghiệm', 'adj', 'Empirical evidence is needed.',
             'Cần có bằng chứng thực nghiệm.', 'experimental, observed'),
            ('phenomenon', 'fɪˈnɒmɪnən', 'hiện tượng', 'n', 'Climate change is a global phenomenon.',
             'Biến đổi khí hậu là hiện tượng toàn cầu.', 'occurrence, event'),
            ('proliferate', 'prəˈlɪfəreɪt', 'sinh sôi, phát triển nhanh', 'v', 'Social media has proliferated rapidly.',
             'Mạng xã hội đã phát triển nhanh chóng.', 'multiply, spread'),
            ('ramification', 'ˌræmɪfɪˈkeɪʃən', 'hệ quả, tác động', 'n', 'Consider the ramifications of this decision.',
             'Xem xét hệ quả của quyết định này.', 'consequence, implication'),
            ('scrutinize', 'ˈskruːtɪnaɪz', 'xem xét kỹ, kiểm tra', 'v', 'The proposal was heavily scrutinized.',
             'Đề xuất đã được xem xét kỹ lưỡng.', 'examine, inspect'),
            ('ubiquitous', 'juːˈbɪkwɪtəs', 'có mặt khắp nơi', 'adj', 'Smartphones are ubiquitous today.',
             'Điện thoại thông minh có mặt khắp nơi ngày nay.', 'omnipresent, widespread'),
        ],
        4: [  # Business
            ('acquisition', 'ˌækwɪˈzɪʃən', 'vụ mua lại, thâu tóm', 'n', 'The acquisition cost $2 billion.',
             'Vụ mua lại có giá 2 tỷ đô la.', 'takeover, buyout'),
            ('benchmark', 'ˈbentʃmɑːrk', 'tiêu chuẩn, chuẩn mực', 'n', 'Set a performance benchmark.',
             'Đặt tiêu chuẩn hiệu suất.', 'standard, reference'),
            ('bottom line', 'ˈbɒtəm laɪn', 'lợi nhuận ròng, điều cốt lõi', 'n', 'Focus on the bottom line.',
             'Tập trung vào lợi nhuận ròng.', 'net profit, core point'),
            ('disruptive', 'dɪsˈrʌptɪv', 'mang tính đột phá', 'adj', 'AI is a disruptive technology.',
             'AI là công nghệ mang tính đột phá.', 'innovative, revolutionary'),
            ('due diligence', 'djuː ˈdɪlɪdʒəns', 'thẩm định, kiểm tra pháp lý', 'n',
             'Conduct due diligence before investing.', 'Thẩm định trước khi đầu tư.', 'investigation, audit'),
            ('equity', 'ˈekwɪti', 'vốn chủ sở hữu, cổ phần', 'n', 'Investors own 40% equity.',
             'Nhà đầu tư sở hữu 40% cổ phần.', 'shares, ownership'),
            ('leverage', 'ˈlevərɪdʒ', 'tận dụng, đòn bẩy tài chính', 'v', 'Leverage your network for growth.',
             'Tận dụng mạng lưới của bạn để phát triển.', 'utilize, exploit'),
            ('pivot', 'ˈpɪvət', 'xoay chuyển chiến lược', 'v', 'The startup had to pivot its model.',
             'Startup phải xoay chuyển mô hình.', 'shift, change direction'),
            ('scalable', 'ˈskeɪləbl', 'có thể mở rộng quy mô', 'adj', 'Build a scalable product.',
             'Xây dựng sản phẩm có thể mở rộng.', 'expandable, flexible'),
            ('synergy', 'ˈsɪnərdʒi', 'sức mạnh tổng hợp', 'n', 'The merger created synergy.',
             'Vụ sáp nhập tạo ra sức mạnh tổng hợp.', 'combined strength'),
            ('venture capital', 'ˈventʃər ˈkæpɪtl', 'vốn đầu tư mạo hiểm', 'n', 'They raised venture capital funding.',
             'Họ đã huy động vốn đầu tư mạo hiểm.', 'VC, startup funding'),
            ('yield', 'jiːld', 'lợi suất, sản lượng', 'n', 'The bond yield is 5%.', 'Lợi suất trái phiếu là 5%.',
             'return, output'),
        ],
        5: [  # Daily
            ('accomplished', 'əˈkɒmplɪʃt', 'tài giỏi, hoàn thành xuất sắc', 'adj', 'She is an accomplished musician.',
             'Cô ấy là nhạc sĩ tài giỏi.', 'skilled, talented'),
            ('awkward', 'ˈɔːkwərd', 'lúng túng, ngượng ngùng', 'adj', 'That was an awkward moment.',
             'Đó là một khoảnh khắc ngượng ngùng.', 'uncomfortable, clumsy'),
            ('chit-chat', 'ˈtʃɪt tʃæt', 'chuyện phiếm, tán gẫu', 'n', 'We made some chit-chat before the meeting.',
             'Chúng tôi tán gẫu trước cuộc họp.', 'small talk, gossip'),
            ('craving', 'ˈkreɪvɪŋ', 'thèm muốn, ao ước', 'n', 'I have a craving for pizza.', 'Tôi đang thèm pizza.',
             'desire, longing'),
            ('ditch', 'dɪtʃ', 'bỏ, từ bỏ (thông tục)', 'v', 'Let\'s ditch the plan and go spontaneously.',
             'Hãy bỏ kế hoạch và đi ngẫu hứng.', 'abandon, drop'),
            ('frugal', 'ˈfruːɡəl', 'tiết kiệm, t검소', 'adj', 'She is very frugal with money.',
             'Cô ấy rất tiết kiệm với tiền bạc.', 'thrifty, economical'),
            ('hang out', 'hæŋ aʊt', 'đi chơi, tụ tập', 'v', 'We hung out at the café all afternoon.',
             'Chúng tôi ngồi cà phê cả buổi chiều.', 'socialize, meet up'),
            ('impulsive', 'ɪmˈpʌlsɪv', 'bốc đồng, bộc phát', 'adj', 'Don\'t make impulsive decisions.',
             'Đừng đưa ra quyết định bốc đồng.', 'spontaneous, rash'),
            ('mellow', 'ˈmeloʊ', 'điềm tĩnh, nhẹ nhàng', 'adj', 'He\'s very mellow after vacation.',
             'Anh ấy rất điềm tĩnh sau kỳ nghỉ.', 'calm, relaxed'),
            ('overwhelmed', 'ˌoʊvərˈwelmd', 'choáng ngợp, bị áp đảo', 'adj', 'I\'m overwhelmed with work.',
             'Tôi bị áp đảo bởi công việc.', 'swamped, inundated'),
            ('procrastinate', 'prəˈkræstɪneɪt', 'trì hoãn, lần lữa', 'v', 'Stop procrastinating and start working.',
             'Thôi trì hoãn và bắt đầu làm việc đi.', 'delay, postpone'),
            ('quirky', 'ˈkwɜːrki', 'kỳ quặc, độc đáo', 'adj', 'She has a quirky sense of humour.',
             'Cô ấy có khiếu hài hước độc đáo.', 'eccentric, unusual'),
            ('spontaneous', 'spɒnˈteɪniəs', 'tự phát, ngẫu hứng', 'adj', 'Let\'s be spontaneous and travel now!',
             'Hãy ngẫu hứng đi du lịch ngay!', 'unplanned, impulsive'),
            ('vibe', 'vaɪb', 'cảm giác, không khí', 'n', 'This place has a great vibe.',
             'Nơi này có không khí tuyệt vời.', 'atmosphere, feeling'),
            ('whine', 'waɪn', 'than vãn, rên rỉ', 'v', 'Stop whining and do something about it.',
             'Thôi than vãn và làm gì đó đi.', 'complain, moan'),
        ],
        6: [  # Academic Writing
            ('accordingly', 'əˈkɔːrdɪŋli', 'theo đó, vì vậy', 'adv',
             'The results were positive; accordingly, we proceeded.', 'Kết quả tích cực; theo đó, chúng tôi tiến hành.',
             'therefore, consequently'),
            ('albeit', 'ɔːlˈbiːɪt', 'mặc dù, dù cho', 'conj', 'The study was useful, albeit limited.',
             'Nghiên cứu hữu ích, mặc dù còn hạn chế.', 'although, even though'),
            ('conversely', 'ˈkɒnvɜːrsli', 'ngược lại, trái lại', 'adv', 'Conversely, some studies show the opposite.',
             'Ngược lại, một số nghiên cứu cho thấy điều ngược lại.', 'on the other hand'),
            ('henceforth', 'ˌhensˈfɔːrθ', 'kể từ đây, từ nay về sau', 'adv',
             'Henceforth, all reports must be submitted digitally.', 'Kể từ đây, tất cả báo cáo phải nộp điện tử.',
             'from now on'),
            ('inherently', 'ɪnˈhɪərəntli', 'vốn dĩ, về cơ bản', 'adv', 'The problem is inherently complex.',
             'Vấn đề vốn dĩ phức tạp.', 'fundamentally, essentially'),
            ('notwithstanding', 'ˌnɒtwɪðˈstændɪŋ', 'mặc dù vậy, bất chấp', 'prep',
             'Notwithstanding the challenges, they succeeded.', 'Mặc dù vậy, họ đã thành công.', 'despite, regardless'),
            ('ostensibly', 'ɒˈstensɪbli', 'có vẻ như, bề ngoài', 'adv', 'Ostensibly, the plan looks feasible.',
             'Có vẻ như kế hoạch trông khả thi.', 'apparently, seemingly'),
            ('preclude', 'prɪˈkluːd', 'ngăn cản, loại trừ', 'v', 'This does not preclude other options.',
             'Điều này không loại trừ các lựa chọn khác.', 'prevent, exclude'),
            ('subsequently', 'ˈsʌbsɪkwəntli', 'sau đó, tiếp theo', 'adv',
             'The data was collected and subsequently analyzed.', 'Dữ liệu được thu thập và sau đó phân tích.',
             'afterwards, later'),
            ('whereby', 'weərˈbaɪ', 'theo đó, qua đó', 'adv', 'A system whereby data is automatically saved.',
             'Một hệ thống qua đó dữ liệu được lưu tự động.', 'through which, by which'),
        ],
        7: [  # Travel
            ('amenities', 'əˈmiːnɪtiz', 'tiện nghi, tiện ích', 'n', 'The hotel has excellent amenities.',
             'Khách sạn có tiện nghi tuyệt vời.', 'facilities, comforts'),
            ('boarding pass', 'ˈbɔːrdɪŋ pæs', 'thẻ lên máy bay', 'n', 'Show your boarding pass at the gate.',
             'Xuất trình thẻ lên máy bay tại cửa.', 'flight ticket stub'),
            ('customs', 'ˈkʌstəmz', 'hải quan', 'n', 'Declare all goods at customs.',
             'Khai báo tất cả hàng hóa tại hải quan.', 'border control'),
            ('expedition', 'ˌekspɪˈdɪʃən', 'chuyến thám hiểm', 'n', 'They went on a mountain expedition.',
             'Họ tham gia một chuyến thám hiểm núi.', 'journey, adventure'),
            ('hostel', 'ˈhɒstəl', 'nhà trọ, ký túc xá', 'n', 'Backpackers stay in hostels.',
             'Người đi phượt ở nhà trọ.', 'budget accommodation'),
            ('itinerary', 'aɪˈtɪnərəri', 'lịch trình, hành trình', 'n', 'Plan your itinerary in advance.',
             'Lên kế hoạch lịch trình trước.', 'schedule, travel plan'),
            ('jet lag', 'dʒet læɡ', 'mệt vì lệch múi giờ', 'n', 'I have terrible jet lag after the flight.',
             'Tôi rất mệt vì lệch múi giờ.', 'time zone fatigue'),
            ('layover', 'ˈleɪoʊvər', 'thời gian chờ nối chuyến', 'n', 'We have a 4-hour layover in Dubai.',
             'Chúng tôi có 4 tiếng chờ ở Dubai.', 'stopover, transit'),
            ('souvenir', 'ˌsuːvəˈnɪr', 'đồ lưu niệm', 'n', 'I bought souvenirs for everyone.',
             'Tôi mua đồ lưu niệm cho tất cả mọi người.', 'keepsake, memento'),
            ('visa', 'ˈviːzə', 'thị thực, visa', 'n', 'Apply for a visa before traveling.',
             'Xin visa trước khi đi du lịch.', 'travel permit'),
        ],
        8: [  # Tech
            ('algorithm', 'ˈælɡərɪðəm', 'thuật toán', 'n', 'The algorithm processes data quickly.',
             'Thuật toán xử lý dữ liệu nhanh chóng.', 'procedure, formula'),
            ('bandwidth', 'ˈbændwɪdθ', 'băng thông', 'n', 'High bandwidth is needed for streaming.',
             'Cần băng thông cao để stream.', 'data capacity'),
            ('cloud computing', 'klaʊd kəmˈpjuːtɪŋ', 'điện toán đám mây', 'n',
             'Store data on cloud computing platforms.', 'Lưu dữ liệu trên nền tảng điện toán đám mây.',
             'remote computing'),
            ('debug', 'diːˈbʌɡ', 'gỡ lỗi, sửa lỗi', 'v', 'The developer spent hours debugging.',
             'Lập trình viên mất nhiều giờ gỡ lỗi.', 'fix, troubleshoot'),
            ('encryption', 'ɪnˈkrɪpʃən', 'mã hóa', 'n', 'Data encryption protects privacy.',
             'Mã hóa dữ liệu bảo vệ quyền riêng tư.', 'encoding, security'),
            ('framework', 'ˈfreɪmwɜːrk', 'khung làm việc, nền tảng', 'n', 'React is a popular JavaScript framework.',
             'React là framework JavaScript phổ biến.', 'platform, structure'),
            ('iteration', 'ˌɪtəˈreɪʃən', 'lần lặp, chu kỳ phát triển', 'n', 'Each iteration improves the product.',
             'Mỗi chu kỳ cải thiện sản phẩm.', 'version, cycle'),
            ('latency', 'ˈleɪtənsi', 'độ trễ', 'n', 'Low latency is critical for gaming.',
             'Độ trễ thấp rất quan trọng với game.', 'delay, lag'),
            ('open source', 'ˈoʊpən sɔːrs', 'mã nguồn mở', 'adj', 'Linux is an open source OS.',
             'Linux là hệ điều hành mã nguồn mở.', 'freely available code'),
            ('scalability', 'ˌskeɪləˈbɪlɪti', 'khả năng mở rộng', 'n', 'Scalability is key for growth.',
             'Khả năng mở rộng là chìa khóa tăng trưởng.', 'expandability'),
            ('syntax', 'ˈsɪntæks', 'cú pháp lập trình', 'n', 'Python has clean syntax.', 'Python có cú pháp sạch.',
             'code structure, grammar'),
            ('virtual reality', 'ˈvɜːrtʃuəl riˈæləti', 'thực tế ảo', 'n', 'VR is transforming gaming.',
             'VR đang thay đổi ngành game.', 'VR, immersive tech'),
        ],
        9: [  # Japanese
            ('ありがとう', 'a·ri·ga·to·u', 'Cảm ơn', 'expression', 'ありがとうございます！', 'Cảm ơn rất nhiều!', ''),
            ('すみません', 'su·mi·ma·sen', 'Xin lỗi / Excuse me', 'expression', 'すみません、道を教えてください。',
             'Xin lỗi, vui lòng chỉ đường cho tôi.', ''),
            ('たべる', 'ta·be·ru', 'ăn', 'verb', 'ごはんをたべます。', 'Tôi ăn cơm.', ''),
            ('みず', 'mi·zu', 'nước', 'noun', 'みずをください。', 'Cho tôi nước.', ''),
            ('でんしゃ', 'den·sha', 'tàu điện', 'noun', 'でんしゃにのります。', 'Tôi đi tàu điện.', ''),
            ('がっこう', 'ga·k·ko·u', 'trường học', 'noun', 'がっこうへいきます。', 'Tôi đến trường.', ''),
            ('ともだち', 'to·mo·da·chi', 'bạn bè', 'noun', 'ともだちとあそびます。', 'Tôi chơi với bạn bè.', ''),
            ('かわいい', 'ka·wa·i·i', 'dễ thương, đáng yêu', 'adj', 'このねこはかわいいです。',
             'Con mèo này dễ thương quá.', ''),
            ('むずかしい', 'mu·zu·ka·shi·i', 'khó', 'adj', 'にほんごはむずかしいです。', 'Tiếng Nhật khó.', ''),
            ('おいしい', 'o·i·shi·i', 'ngon', 'adj', 'このりょうりはおいしいです。', 'Món ăn này ngon lắm.', ''),
        ],
        10: [  # Korean
            ('안녕하세요', 'an·nyeong·ha·se·yo', 'Xin chào (lịch sự)', 'expression', '안녕하세요, 만나서 반갑습니다.',
             'Xin chào, rất vui được gặp bạn.', ''),
            ('감사합니다', 'gam·sa·ham·ni·da', 'Cảm ơn (lịch sự)', 'expression', '도와주셔서 감사합니다.', 'Cảm ơn vì đã giúp đỡ.',
             ''),
            ('사랑해요', 'sa·rang·hae·yo', 'Tôi yêu bạn', 'expression', '당신을 사랑해요.', 'Tôi yêu bạn.', ''),
            ('맛있어요', 'ma·si·sseo·yo', 'Ngon lắm', 'adj', '이 음식은 정말 맛있어요.', 'Món ăn này ngon thật sự.', ''),
            ('학교', 'hak·gyo', 'trường học', 'noun', '학교에 가요.', 'Tôi đi học.', ''),
            ('친구', 'chin·gu', 'bạn bè', 'noun', '친구를 만나요.', 'Tôi gặp bạn.', ''),
            ('가족', 'ga·jok', 'gia đình', 'noun', '가족이 제일 중요해요.', 'Gia đình là quan trọng nhất.', ''),
            ('예쁘다', 'ye·ppeu·da', 'đẹp (của phụ nữ)', 'adj', '그녀는 정말 예뻐요.', 'Cô ấy thật đẹp.', ''),
            ('바쁘다', 'ba·ppeu·da', 'bận rộn', 'adj', '요즘 너무 바빠요.', 'Dạo này tôi rất bận.', ''),
            ('재미있어요', 'jae·mi·i·sseo·yo', 'thú vị, vui', 'adj', '한국어 공부가 재미있어요.', 'Học tiếng Hàn rất thú vị.', ''),
        ],
    }

    for deck_id, words in all_words.items():
        for idx, w in enumerate(words):
            exists = c.execute("SELECT id FROM words WHERE deck_id=? AND word=?", (deck_id, w[0])).fetchone()
            if not exists:
                c.execute(
                    "INSERT INTO words(deck_id,word,pronunciation,meaning,part_of_speech,example,example_vn,synonyms,order_idx) VALUES(?,?,?,?,?,?,?,?,?)",
                    (deck_id, w[0], w[1], w[2], w[3], w[4], w[5], w[6], idx))
    c.execute("UPDATE decks SET word_count=(SELECT COUNT(*) FROM words WHERE deck_id=decks.id)")


# ── AUTH ─────────────────────────────────────────────────────
def login_required(f):
    @functools.wraps(f)
    def w(*a, **kw):
        if 'uid' not in session: return redirect(url_for('login'))
        return f(*a, **kw)

    return w


def admin_required(f):
    @functools.wraps(f)
    def w(*a, **kw):
        if 'uid' not in session: return redirect(url_for('login'))
        if session.get('role') != 'admin': return redirect(url_for('home'))
        return f(*a, **kw)

    return w


def me():
    if 'uid' not in session: return None
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (session['uid'],)).fetchone()
    conn.close()
    return u


@app.context_processor
def helpers():
    def lang_label(code): return {'en': '🇬🇧 Anh', 'ja': '🇯🇵 Nhật', 'ko': '🇰🇷 Hàn', 'fr': '🇫🇷 Pháp'}.get(code, code)

    def level_label(l): return {'beginner': 'Cơ bản', 'intermediate': 'Trung cấp', 'advanced': 'Nâng cao'}.get(l, l)

    def mode_label(m): return {'flashcard': 'Flashcard', 'quiz': 'Quiz', 'typing': 'Typing', 'scramble': 'Scramble',
                               'speedmatch': 'Speed Match', 'memorypairs': 'Memory Pairs', 'wordbomb': 'Word Bomb'}.get(
        m, m)

    def cover_bg(lang, color):
        return f"background:{color};"

    return dict(lang_label=lang_label, level_label=level_label, mode_label=mode_label, cover_bg=cover_bg)


# ── AUTH ROUTES ───────────────────────────────────────────────
@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'uid' in session: return redirect(url_for('home'))
    error = None
    if request.method == 'POST':
        un = request.form.get('username', '').strip()
        pw = request.form.get('password', '')
        conn = get_db()
        u = conn.execute("SELECT * FROM users WHERE username=?", (un,)).fetchone()
        conn.close()
        if not u:
            error = 'Tài khoản không tồn tại'
        elif not u['is_active']:
            error = 'Tài khoản bị khoá'
        elif not check_password_hash(u['password'], pw):
            error = 'Mật khẩu không đúng'
        else:
            session.update({'uid': u['id'], 'username': u['username'], 'role': u['role']})
            return redirect(url_for('home'))
    return render_template('login.html', error=error)


@app.route('/register', methods=['GET', 'POST'])
def register():
    error = None
    if request.method == 'POST':
        un = request.form.get('username', '').strip()
        pw = request.form.get('password', '')
        avatar = request.form.get('avatar', '🧑')
        if len(un) < 3:
            error = 'Username phải có ít nhất 3 ký tự'
        elif len(pw) < 4:
            error = 'Mật khẩu phải có ít nhất 4 ký tự'
        else:
            conn = get_db()
            try:
                conn.execute("INSERT INTO users(username,password,avatar) VALUES(?,?,?)",
                             (un, generate_password_hash(pw), avatar))
                conn.commit()
                flash('Đăng ký thành công!', 'success')
                return redirect(url_for('login'))
            except:
                error = 'Username đã tồn tại'
            finally:
                conn.close()
    return render_template('register.html', error=error)


@app.route('/logout')
def logout():
    session.clear();
    return redirect(url_for('login'))


# ── MAIN PAGES ────────────────────────────────────────────────
@app.route('/')
@login_required
def home():
    u = me()
    conn = get_db()
    decks = conn.execute("""
        SELECT d.*, CASE WHEN ud.user_id IS NOT NULL THEN 1 ELSE 0 END as in_lib,
               (SELECT COUNT(*) FROM study_progress WHERE user_id=? AND deck_id=d.id AND status='mastered') as mastered
        FROM decks d LEFT JOIN user_decks ud ON d.id=ud.deck_id AND ud.user_id=?
        WHERE d.is_public=1 ORDER BY d.download_count DESC
    """, (u['id'], u['id'])).fetchall()
    my_decks = conn.execute("""
        SELECT d.*,
          (SELECT COUNT(*) FROM study_progress WHERE user_id=? AND deck_id=d.id AND status IN ('learning','mastered')) as learned
        FROM decks d JOIN user_decks ud ON d.id=ud.deck_id AND ud.user_id=?
    """, (u['id'], u['id'])).fetchall()
    leaderboard = conn.execute(
        "SELECT username,avatar,xp,streak FROM users WHERE is_active=1 ORDER BY xp DESC LIMIT 10").fetchall()
    recent_scores = conn.execute("""
        SELECT gs.*, d.name as dname, d.emoji FROM game_scores gs
        LEFT JOIN decks d ON gs.deck_id=d.id
        WHERE gs.user_id=? ORDER BY gs.created_at DESC LIMIT 6
    """, (u['id'],)).fetchall()
    total_words = conn.execute("SELECT COUNT(*) FROM study_progress WHERE user_id=?", (u['id'],)).fetchone()[0]
    mastered = \
    conn.execute("SELECT COUNT(*) FROM study_progress WHERE user_id=? AND status='mastered'", (u['id'],)).fetchone()[0]
    conn.close()
    return render_template('home.html', u=dict(u), decks=[dict(d) for d in decks],
                           my_decks=[dict(d) for d in my_decks],
                           leaderboard=[dict(r) for r in leaderboard],
                           recent_scores=[dict(r) for r in recent_scores],
                           total_words=total_words, mastered=mastered)


@app.route('/deck/<int:did>')
@login_required
def deck(did):
    u = me()
    conn = get_db()
    d = conn.execute("SELECT * FROM decks WHERE id=?", (did,)).fetchone()
    if not d: return "Not found", 404
    words = conn.execute("""
        SELECT w.*, sp.status, sp.correct_count, sp.wrong_count
        FROM words w LEFT JOIN study_progress sp ON sp.word_id=w.id AND sp.user_id=?
        WHERE w.deck_id=? ORDER BY w.order_idx
    """, (u['id'], did)).fetchall()
    in_lib = conn.execute("SELECT 1 FROM user_decks WHERE user_id=? AND deck_id=?", (u['id'], did)).fetchone()
    stats = conn.execute("""
        SELECT COUNT(*) as total,
          SUM(CASE WHEN sp.status='new' OR sp.status IS NULL THEN 1 ELSE 0 END) as new_w,
          SUM(CASE WHEN sp.status='learning' THEN 1 ELSE 0 END) as learning,
          SUM(CASE WHEN sp.status='mastered' THEN 1 ELSE 0 END) as mastered
        FROM words w LEFT JOIN study_progress sp ON sp.word_id=w.id AND sp.user_id=?
        WHERE w.deck_id=?
    """, (u['id'], did)).fetchone()
    conn.close()
    return render_template('deck.html', u=dict(u), d=dict(d),
                           words=[dict(w) for w in words],
                           in_lib=bool(in_lib), stats=dict(stats) if stats else {})


# ── GAME ROUTES ───────────────────────────────────────────────
@app.route('/game/<game>/<int:did>')
@login_required
def game(game, did):
    games = ['flashcard', 'quiz', 'typing', 'scramble', 'speedmatch', 'memorypairs', 'wordbomb']
    if game not in games: return "Invalid game", 400
    u = me()
    conn = get_db()
    d = conn.execute("SELECT * FROM decks WHERE id=?", (did,)).fetchone()
    words = conn.execute("SELECT * FROM words WHERE deck_id=? ORDER BY order_idx", (did,)).fetchall()
    conn.close()
    if len(words) < 2: return redirect(url_for('deck', did=did))
    return render_template(f'games/{game}.html', u=dict(u), d=dict(d), words=[dict(w) for w in words])


@app.route('/games')
@login_required
def games_hub():
    u = me()
    conn = get_db()
    my_decks = conn.execute("""
        SELECT d.* FROM decks d JOIN user_decks ud ON d.id=ud.deck_id AND ud.user_id=?
    """, (u['id'],)).fetchall()
    top_scores = conn.execute("""
        SELECT gs.game, gs.score, gs.created_at, u.username, u.avatar, d.name as dname
        FROM game_scores gs JOIN users u ON gs.user_id=u.id
        LEFT JOIN decks d ON gs.deck_id=d.id
        ORDER BY gs.score DESC LIMIT 20
    """).fetchall()
    conn.close()
    return render_template('games_hub.html', u=dict(u),
                           my_decks=[dict(d) for d in my_decks],
                           top_scores=[dict(r) for r in top_scores])


# ── API ───────────────────────────────────────────────────────
@app.route('/api/add_deck/<int:did>', methods=['POST'])
@login_required
def add_deck(did):
    u = me()
    conn = get_db()
    try:
        conn.execute("INSERT INTO user_decks(user_id,deck_id) VALUES(?,?)", (u['id'], did))
        conn.execute("UPDATE decks SET download_count=download_count+1 WHERE id=?", (did,))
        words = conn.execute("SELECT id FROM words WHERE deck_id=?", (did,)).fetchall()
        for w in words:
            conn.execute("INSERT OR IGNORE INTO study_progress(user_id,word_id,deck_id,status) VALUES(?,?,?,?)",
                         (u['id'], w['id'], did, 'new'))
        conn.commit()
        return jsonify({'ok': True})
    except:
        return jsonify({'ok': False, 'msg': 'Đã có trong thư viện'})
    finally:
        conn.close()


@app.route('/api/remove_deck/<int:did>', methods=['POST'])
@login_required
def remove_deck(did):
    u = me()
    conn = get_db()
    conn.execute("DELETE FROM user_decks WHERE user_id=? AND deck_id=?", (u['id'], did))
    conn.commit();
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/progress', methods=['POST'])
@login_required
def update_progress():
    data = request.json
    u = me()
    conn = get_db()
    wid, did, correct = data['word_id'], data['deck_id'], data['correct']
    ex = conn.execute("SELECT * FROM study_progress WHERE user_id=? AND word_id=?", (u['id'], wid)).fetchone()
    if ex:
        nc = ex['correct_count'] + (1 if correct else 0)
        status = 'mastered' if nc >= 3 else 'learning'
        if not correct: status = 'learning'
        conn.execute(
            "UPDATE study_progress SET correct_count=?,wrong_count=wrong_count+?,status=?,last_studied=CURRENT_TIMESTAMP WHERE user_id=? AND word_id=?",
            (nc, 0 if correct else 1, status, u['id'], wid))
    else:
        conn.execute(
            "INSERT INTO study_progress(user_id,word_id,deck_id,status,correct_count,wrong_count,last_studied) VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)",
            (u['id'], wid, did, 'learning', 1 if correct else 0, 0 if correct else 1))
    conn.commit();
    conn.close()
    return jsonify({'ok': True})


@app.route('/api/save_score', methods=['POST'])
@login_required
def save_score():
    data = request.json
    u = me()
    xp = min(data.get('score', 0) // 5, 200)
    conn = get_db()
    conn.execute("INSERT INTO game_scores(user_id,deck_id,game,score,duration_sec,xp_earned) VALUES(?,?,?,?,?,?)",
                 (u['id'], data.get('deck_id'), data['game'], data['score'], data.get('duration', 0), xp))
    conn.execute("UPDATE users SET xp=xp+?,gems=gems+? WHERE id=?", (xp, max(xp // 10, 1), u['id']))
    today = date.today().isoformat()
    user_row = conn.execute("SELECT last_study,streak FROM users WHERE id=?", (u['id'],)).fetchone()
    if user_row['last_study'] != today:
        new_streak = (user_row['streak'] or 0) + 1
        conn.execute("UPDATE users SET streak=?,max_streak=MAX(max_streak,?),last_study=? WHERE id=?",
                     (new_streak, new_streak, today, u['id']))
    conn.commit()
    u2 = conn.execute("SELECT xp,gems,streak FROM users WHERE id=?", (u['id'],)).fetchone()
    conn.close()
    return jsonify({'ok': True, 'xp': u2['xp'], 'xp_earned': xp, 'gems': u2['gems'], 'streak': u2['streak']})


@app.route('/api/stats')
@login_required
def stats():
    u = me()
    return jsonify({'xp': u['xp'], 'streak': u['streak'], 'gems': u['gems']})


@app.route('/api/words/<int:did>')
@login_required
def api_words(did):
    conn = get_db()
    words = conn.execute("SELECT * FROM words WHERE deck_id=? ORDER BY order_idx", (did,)).fetchall()
    conn.close()
    return jsonify([dict(w) for w in words])


# ── DOWNLOADS ─────────────────────────────────────────────────
@app.route('/dl/<int:did>/<fmt>')
@login_required
def download(did, fmt):
    conn = get_db()
    d = conn.execute("SELECT * FROM decks WHERE id=?", (did,)).fetchone()
    words = conn.execute("SELECT * FROM words WHERE deck_id=? ORDER BY order_idx", (did,)).fetchall()
    conn.close()
    name = d['name'].replace(' ', '_')
    if fmt == 'csv':
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(['Từ vựng', 'Phiên âm', 'Nghĩa', 'Loại từ', 'Ví dụ', 'Dịch ví dụ', 'Từ đồng nghĩa'])
        for row in words: w.writerow(
            [row['word'], row['pronunciation'], row['meaning'], row['part_of_speech'], row['example'],
             row['example_vn'], row['synonyms']])
        out.seek(0)
        return Response('\ufeff' + out.getvalue(), mimetype='text/csv; charset=utf-8',
                        headers={'Content-Disposition': f'attachment;filename="{name}.csv"'})
    elif fmt == 'json':
        data = {'deck': dict(d), 'words': [dict(w) for w in words]}
        return Response(json.dumps(data, ensure_ascii=False, indent=2), mimetype='application/json',
                        headers={'Content-Disposition': f'attachment;filename="{name}.json"'})
    elif fmt == 'anki':
        out = io.StringIO()
        for row in words:
            front = f"{row['word']}\n[{row['pronunciation']}]"
            back = f"{row['meaning']}\n{row['example']}\n{row['example_vn']}"
            out.write(f"{front}\t{back}\n")
        out.seek(0)
        return Response('\ufeff' + out.getvalue(), mimetype='text/plain; charset=utf-8',
                        headers={'Content-Disposition': f'attachment;filename="{name}_anki.txt"'})
    return "Invalid format", 400


# ── ADMIN ─────────────────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin():
    conn = get_db()
    users = [dict(r) for r in conn.execute("SELECT * FROM users ORDER BY xp DESC").fetchall()]
    decks = [dict(r) for r in conn.execute(
        "SELECT d.*,(SELECT COUNT(*) FROM words WHERE deck_id=d.id) as wc FROM decks d ORDER BY id").fetchall()]
    total_games = conn.execute("SELECT COUNT(*) FROM game_scores").fetchone()[0]
    conn.close()
    return render_template('admin/dashboard.html', u=dict(me()), users=users, decks=decks, total_games=total_games)


@app.route('/admin/decks/add', methods=['POST'])
@admin_required
def admin_add_deck():
    data = request.json
    conn = get_db()
    conn.execute(
        "INSERT INTO decks(name,description,language,level,category,emoji,color,is_public,created_by) VALUES(?,?,?,?,?,?,?,?,?)",
        (data['name'], data.get('desc', ''), data.get('lang', 'en'), data.get('level', 'beginner'),
         data.get('category', 'general'), data.get('emoji', '📚'), data.get('color', '#2ECC71'), 1, session['uid']))
    conn.commit();
    conn.close()
    return jsonify({'ok': True})


@app.route('/admin/decks/<int:did>/delete', methods=['POST'])
@admin_required
def admin_del_deck(did):
    conn = get_db()
    conn.execute("DELETE FROM decks WHERE id=?", (did,))
    conn.commit();
    conn.close()
    return jsonify({'ok': True})


@app.route('/admin/words/<int:did>')
@admin_required
def admin_words(did):
    conn = get_db()
    d = dict(conn.execute("SELECT * FROM decks WHERE id=?", (did,)).fetchone())
    words = [dict(r) for r in conn.execute("SELECT * FROM words WHERE deck_id=? ORDER BY order_idx", (did,)).fetchall()]
    conn.close()
    return render_template('admin/words.html', u=dict(me()), d=d, words=words)


@app.route('/admin/words/add', methods=['POST'])
@admin_required
def admin_add_word():
    data = request.json
    conn = get_db()
    conn.execute(
        "INSERT INTO words(deck_id,word,pronunciation,meaning,part_of_speech,example,example_vn,synonyms) VALUES(?,?,?,?,?,?,?,?)",
        (data['did'], data['word'], data.get('pron', ''), data['meaning'], data.get('pos', 'word'),
         data.get('ex', ''), data.get('exvn', ''), data.get('syn', '')))
    conn.execute("UPDATE decks SET word_count=(SELECT COUNT(*) FROM words WHERE deck_id=?) WHERE id=?",
                 (data['did'], data['did']))
    conn.commit();
    conn.close()
    return jsonify({'ok': True})


@app.route('/admin/words/<int:wid>/delete', methods=['POST'])
@admin_required
def admin_del_word(wid):
    conn = get_db()
    did = conn.execute("SELECT deck_id FROM words WHERE id=?", (wid,)).fetchone()['deck_id']
    conn.execute("DELETE FROM words WHERE id=?", (wid,))
    conn.execute("UPDATE decks SET word_count=(SELECT COUNT(*) FROM words WHERE deck_id=?) WHERE id=?", (did, did))
    conn.commit();
    conn.close()
    return jsonify({'ok': True})

@app.route('/admin/words/<int:wid>/edit', methods=['POST'])
@admin_required
def admin_edit_word(wid):
    conn = get_db()
    d = request.get_json()
    conn.execute(
        "UPDATE words SET word=?,pronunciation=?,meaning=?,part_of_speech=?,synonyms=?,example=?,example_vn=? WHERE id=?",
        (d.get('word',''), d.get('pron',''), d.get('meaning',''), d.get('pos',''),
         d.get('syn',''), d.get('ex',''), d.get('exvn',''), wid)
    )
    conn.commit(); conn.close()
    return jsonify({'ok': True})

@app.route('/admin/users/<int:uid>/toggle', methods=['POST'])
@admin_required
def admin_toggle(uid):
    if uid == session.get('uid'):
        return jsonify({'ok': False, 'error': 'cannot_toggle_self'}), 400
    conn = get_db()
    conn.execute("UPDATE users SET is_active=1-is_active WHERE id=?", (uid,))
    conn.commit()
    u = conn.execute("SELECT is_active FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return jsonify({'ok': True, 'is_active': u['is_active']})


# ═══════════════════════════════════════════════════════════════
# USER DASHBOARD, ACHIEVEMENTS, DAILY CHALLENGE
# ═══════════════════════════════════════════════════════════════

ACHIEVEMENT_LIST = [
    ('first_word', '🌱', 'Bước đầu tiên', 'Học từ đầu tiên'),
    ('words_10', '📖', '10 từ đầu tiên', 'Học được 10 từ'),
    ('words_50', '📚', 'Mọt sách', 'Học được 50 từ'),
    ('words_100', '🎓', 'Học giả', 'Học được 100 từ'),
    ('words_500', '🏛️', 'Bách khoa', 'Học được 500 từ'),
    ('mastered_10', '⭐', 'Ghi nhớ tốt', 'Thuộc 10 từ'),
    ('mastered_50', '🌟', 'Siêu trí nhớ', 'Thuộc 50 từ'),
    ('streak_3', '🔥', 'On fire!', '3 ngày liên tiếp'),
    ('streak_7', '💫', 'Tuần hoàn hảo', '7 ngày liên tiếp'),
    ('streak_30', '🏆', 'Tháng bền bỉ', '30 ngày liên tiếp'),
    ('game_first', '🎮', 'Game thủ', 'Chơi game lần đầu'),
    ('game_10', '🕹️', 'Nghiện game', 'Chơi 10 game'),
    ('perfect_quiz', '💯', 'Hoàn hảo', 'Quiz 100% đúng'),
    ('speed_demon', '⚡', 'Tốc độ ánh sáng', 'Speed Match >200 điểm'),
    ('deck_first', '📦', 'Khởi đầu', 'Thêm bộ từ đầu tiên'),
    ('deck_5', '🗂️', 'Sưu tập gia', 'Học 5 bộ từ khác nhau'),
    ('download', '📥', 'Chia sẻ kiến thức', 'Tải xuống bộ từ'),
    ('daily_3', '🗓️', 'Thói quen tốt', 'Hoàn thành 3 Daily Challenge'),
    ('daily_7', '📅', 'Kỷ luật', 'Hoàn thành 7 Daily Challenge'),
    ('bomb_survive', '💣', 'Chuyên gia bom', 'Qua 10 vòng Word Bomb'),
]


def check_achievements(user_id):
    """Check and grant new achievements"""
    conn = get_db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (user_id,)).fetchone()
    earned_codes = {r['code'] for r in
                    conn.execute("SELECT code FROM achievements WHERE user_id=?", (user_id,)).fetchall()}

    new_achievements = []

    total_studied = conn.execute("SELECT COUNT(*) FROM study_progress WHERE user_id=?", (user_id,)).fetchone()[0]
    mastered = \
    conn.execute("SELECT COUNT(*) FROM study_progress WHERE user_id=? AND status='mastered'", (user_id,)).fetchone()[0]
    game_count = conn.execute("SELECT COUNT(*) FROM game_scores WHERE user_id=?", (user_id,)).fetchone()[0]
    deck_count = conn.execute("SELECT COUNT(*) FROM user_decks WHERE user_id=?", (user_id,)).fetchone()[0]
    perfect = conn.execute("SELECT COUNT(*) FROM game_scores WHERE user_id=? AND game='quiz' AND score>=100",
                           (user_id,)).fetchone()[0]
    speed = \
    conn.execute("SELECT MAX(score) FROM game_scores WHERE user_id=? AND game='speedmatch'", (user_id,)).fetchone()[
        0] or 0
    bomb_best = \
    conn.execute("SELECT MAX(score) FROM game_scores WHERE user_id=? AND game='wordbomb'", (user_id,)).fetchone()[
        0] or 0
    daily_done = \
    conn.execute("SELECT COUNT(*) FROM daily_challenge_completions WHERE user_id=?", (user_id,)).fetchone()[0]
    streak = u['streak'] or 0

    checks = [
        ('first_word', total_studied >= 1),
        ('words_10', total_studied >= 10),
        ('words_50', total_studied >= 50),
        ('words_100', total_studied >= 100),
        ('words_500', total_studied >= 500),
        ('mastered_10', mastered >= 10),
        ('mastered_50', mastered >= 50),
        ('streak_3', streak >= 3),
        ('streak_7', streak >= 7),
        ('streak_30', streak >= 30),
        ('game_first', game_count >= 1),
        ('game_10', game_count >= 10),
        ('perfect_quiz', perfect >= 1),
        ('speed_demon', speed >= 200),
        ('deck_first', deck_count >= 1),
        ('deck_5', deck_count >= 5),
        ('daily_3', daily_done >= 3),
        ('daily_7', daily_done >= 7),
        ('bomb_survive', bomb_best >= 100),
    ]

    ach_map = {a[0]: a for a in ACHIEVEMENT_LIST}
    for code, condition in checks:
        if condition and code not in earned_codes:
            info = ach_map.get(code, (code, '🏆', code, ''))
            conn.execute("INSERT OR IGNORE INTO achievements(user_id,code,name,description,icon) VALUES(?,?,?,?,?)",
                         (user_id, code, info[2], info[3], info[1]))
            new_achievements.append({'code': code, 'icon': info[1], 'name': info[2]})

    conn.commit()
    conn.close()
    return new_achievements


def update_study_log(user_id, xp=0, words=0):
    today = date.today().isoformat()
    conn = get_db()
    conn.execute("""INSERT INTO study_log(user_id, date, words_studied, xp_earned) VALUES(?,?,?,?)
                    ON CONFLICT(user_id, date) DO UPDATE SET words_studied=words_studied+?, xp_earned=xp_earned+?""",
                 (user_id, today, words, xp, words, xp))
    conn.commit()
    conn.close()


@app.route('/profile')
@login_required
def profile():
    u = me()
    conn = get_db()
    # Achievements
    achievements = [dict(r) for r in conn.execute("SELECT * FROM achievements WHERE user_id=? ORDER BY earned_at DESC",
                                                  (u['id'],)).fetchall()]
    earned_codes = {a['code'] for a in achievements}
    all_achievements = [{'code': a[0], 'icon': a[1], 'name': a[2], 'desc': a[3],
                         'earned': a[0] in earned_codes} for a in ACHIEVEMENT_LIST]
    # Study log for last 52 weeks (heatmap)
    study_log = conn.execute("""
        SELECT date, words_studied, xp_earned FROM study_log
        WHERE user_id=? ORDER BY date DESC LIMIT 365
    """, (u['id'],)).fetchall()
    log_dict = {r['date']: {'words': r['words_studied'], 'xp': r['xp_earned']} for r in study_log}
    # Stats
    total_words = conn.execute("SELECT COUNT(*) FROM study_progress WHERE user_id=?", (u['id'],)).fetchone()[0]
    mastered = \
    conn.execute("SELECT COUNT(*) FROM study_progress WHERE user_id=? AND status='mastered'", (u['id'],)).fetchone()[0]
    learning = \
    conn.execute("SELECT COUNT(*) FROM study_progress WHERE user_id=? AND status='learning'", (u['id'],)).fetchone()[0]
    total_games = conn.execute("SELECT COUNT(*) FROM game_scores WHERE user_id=?", (u['id'],)).fetchone()[0]
    total_xp_games = \
    conn.execute("SELECT COALESCE(SUM(xp_earned),0) FROM game_scores WHERE user_id=?", (u['id'],)).fetchone()[0]
    best_scores = [dict(r) for r in conn.execute("""
        SELECT game, MAX(score) as best FROM game_scores WHERE user_id=? GROUP BY game
    """, (u['id'],)).fetchall()]
    # Weekly stats (last 30 days for chart)
    weekly = [dict(r) for r in conn.execute("""
        SELECT date, words_studied, xp_earned FROM study_log
        WHERE user_id=? AND date >= date('now','-29 days') ORDER BY date
    """, (u['id'],)).fetchall()]
    # Decks with progress
    my_decks = [dict(r) for r in conn.execute("""
        SELECT d.*,
          (SELECT COUNT(*) FROM study_progress WHERE user_id=? AND deck_id=d.id AND status='mastered') as mastered_w,
          (SELECT COUNT(*) FROM study_progress WHERE user_id=? AND deck_id=d.id) as total_w
        FROM decks d JOIN user_decks ud ON d.id=ud.deck_id AND ud.user_id=?
    """, (u['id'], u['id'], u['id'])).fetchall()]
    conn.close()
    # Convert u to dict for JSON safety
    u_dict = dict(u)
    return render_template('profile.html', u=u_dict,
                           achievements=achievements, all_achievements=all_achievements,
                           log_dict=log_dict, study_log=study_log,
                           total_words=total_words, mastered=mastered, learning=learning,
                           total_games=total_games, total_xp_games=total_xp_games,
                           best_scores=best_scores, weekly=weekly, my_decks=my_decks)


@app.route('/daily')
@login_required
def daily_challenge():
    u = me()
    today = date.today().isoformat()
    conn = get_db()
    # Get or create today's challenge
    challenge = conn.execute("SELECT * FROM daily_challenges WHERE date=?", (today,)).fetchone()
    if not challenge:
        # Pick a random word from a random public deck
        word = conn.execute("""
            SELECT w.* FROM words w JOIN decks d ON w.deck_id=d.id
            WHERE d.is_public=1 AND d.language='en' ORDER BY RANDOM() LIMIT 1
        """).fetchone()
        if word:
            conn.execute(
                "INSERT OR IGNORE INTO daily_challenges(date, deck_id, word_id, challenge_type) VALUES(?,?,?,?)",
                (today, word['deck_id'], word['id'], 'quiz'))
            conn.commit()
            challenge = conn.execute("SELECT * FROM daily_challenges WHERE date=?", (today,)).fetchone()

    already_done = None
    if challenge:
        already_done = conn.execute(
            "SELECT * FROM daily_challenge_completions WHERE user_id=? AND challenge_id=?",
            (u['id'], challenge['id'])
        ).fetchone()

    # Get challenge word + 4 options
    challenge_word = None
    options = []
    if challenge:
        challenge_word = conn.execute("SELECT * FROM words WHERE id=?", (challenge['word_id'],)).fetchone()
        if challenge_word:
            wrong_opts = conn.execute("""
                SELECT meaning FROM words WHERE id!=? AND deck_id=? ORDER BY RANDOM() LIMIT 3
            """, (challenge_word['id'], challenge_word['deck_id'])).fetchall()
            options = [challenge_word['meaning']] + [r['meaning'] for r in wrong_opts]
            random.shuffle(options)

    # Recent completions leaderboard
    leaderboard = conn.execute("""
        SELECT u.username, u.avatar, dcc.score, dcc.xp_earned, dcc.completed_at
        FROM daily_challenge_completions dcc JOIN users u ON dcc.user_id=u.id
        WHERE dcc.challenge_id=? ORDER BY dcc.score DESC LIMIT 10
    """, (challenge['id'],) if challenge else (0,)).fetchall()

    conn.close()
    return render_template('daily.html', u=dict(u), today=today,
                           challenge=dict(challenge) if challenge else None,
                           challenge_word=dict(challenge_word) if challenge_word else None,
                           options=options, already_done=bool(already_done),
                           leaderboard=[dict(r) for r in leaderboard])


@app.route('/api/complete_daily', methods=['POST'])
@login_required
def complete_daily():
    data = request.json
    u = me()
    challenge_id = data.get('challenge_id')
    score = data.get('score', 0)
    xp = 50 + score  # Bonus XP for daily
    conn = get_db()
    try:
        conn.execute("INSERT INTO daily_challenge_completions(user_id,challenge_id,score,xp_earned) VALUES(?,?,?,?)",
                     (u['id'], challenge_id, score, xp))
        conn.execute("UPDATE users SET xp=xp+?,gems=gems+10 WHERE id=?", (xp, u['id']))
        conn.commit()
        update_study_log(u['id'], xp=xp, words=1)
        new_ach = check_achievements(u['id'])
        u2 = conn.execute("SELECT xp, gems FROM users WHERE id=?", (u['id'],)).fetchone()
        conn.close()
        return jsonify(
            {'ok': True, 'xp_earned': xp, 'total_xp': u2['xp'], 'gems': u2['gems'], 'new_achievements': new_ach})
    except:
        conn.close()
        return jsonify({'ok': False, 'msg': 'Already completed'})


@app.route('/api/achievements')
@login_required
def get_achievements():
    u = me()
    new_ach = check_achievements(u['id'])
    return jsonify({'new': new_ach})


# Override save_score to also update log & check achievements
@app.route('/api/save_score_v2', methods=['POST'])
@login_required
def save_score_v2():
    data = request.json
    u = me()
    xp = min(data.get('score', 0) // 5, 200)
    conn = get_db()
    conn.execute("INSERT INTO game_scores(user_id,deck_id,game,score,duration_sec,xp_earned) VALUES(?,?,?,?,?,?)",
                 (u['id'], data.get('deck_id'), data['game'], data['score'], data.get('duration', 0), xp))
    conn.execute("UPDATE users SET xp=xp+?,gems=gems+? WHERE id=?", (xp, max(xp // 10, 1), u['id']))
    today = date.today().isoformat()
    user_row = conn.execute("SELECT last_study,streak FROM users WHERE id=?", (u['id'],)).fetchone()
    if user_row['last_study'] != today:
        new_streak = (user_row['streak'] or 0) + 1
        conn.execute("UPDATE users SET streak=?,max_streak=MAX(max_streak,?),last_study=? WHERE id=?",
                     (new_streak, new_streak, today, u['id']))
    conn.commit()
    update_study_log(u['id'], xp=xp, words=data.get('words_studied', 0))
    new_ach = check_achievements(u['id'])
    u2 = conn.execute("SELECT xp,gems,streak FROM users WHERE id=?", (u['id'],)).fetchone()
    conn.close()
    return jsonify({'ok': True, 'xp': u2['xp'], 'xp_earned': xp, 'gems': u2['gems'], 'streak': u2['streak'],
                    'new_achievements': new_ach})


# ═══════════════════════════════════════════════════════════════
# SPACED REPETITION (SM-2 Algorithm)
# ═══════════════════════════════════════════════════════════════

import math
from datetime import datetime, date, timedelta


def sm2(ease_factor, interval, repetitions, quality):
    """
    SM-2 Spaced Repetition Algorithm
    quality: 0-5 (0=blackout, 3=correct with difficulty, 5=perfect)
    Returns: (new_interval_days, new_ease_factor, new_repetitions)
    """
    if quality < 3:
        repetitions = 0
        interval = 1
    else:
        if repetitions == 0:
            interval = 1
        elif repetitions == 1:
            interval = 6
        else:
            interval = round(interval * ease_factor)
        repetitions += 1

    ease_factor = max(1.3, ease_factor + 0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    next_review = datetime.now() + timedelta(days=interval)
    return interval, round(ease_factor, 2), repetitions, next_review


@app.route('/review')
@login_required
def review():
    u = me()
    conn = get_db()
    # Words due for review (next_review <= now OR new words)
    due = conn.execute("""
        SELECT sp.*, w.word, w.pronunciation, w.meaning, w.example,
               w.example_vn, w.part_of_speech, w.synonyms,
               d.name as deck_name, d.emoji as deck_emoji, d.language
        FROM study_progress sp
        JOIN words w ON sp.word_id = w.id
        JOIN decks d ON sp.deck_id = d.id
        WHERE sp.user_id = ?
          AND (sp.next_review IS NULL OR sp.next_review <= datetime('now'))
        ORDER BY CASE WHEN sp.next_review IS NULL THEN 0 ELSE 1 END,
                 sp.next_review ASC
        LIMIT 20
    """, (u['id'],)).fetchall()

    # Stats
    total_due = conn.execute("""
        SELECT COUNT(*) FROM study_progress
        WHERE user_id=? AND (next_review IS NULL OR next_review <= datetime('now'))
    """, (u['id'],)).fetchone()[0]

    upcoming = conn.execute("""
        SELECT COUNT(*) FROM study_progress
        WHERE user_id=? AND next_review > datetime('now')
    """, (u['id'],)).fetchone()[0]

    # Interval distribution
    intervals = conn.execute("""
        SELECT
          SUM(CASE WHEN sr_interval IS NULL OR sr_interval=0 THEN 1 ELSE 0 END) as new_w,
          SUM(CASE WHEN sr_interval BETWEEN 1 AND 3 THEN 1 ELSE 0 END) as day3,
          SUM(CASE WHEN sr_interval BETWEEN 4 AND 7 THEN 1 ELSE 0 END) as week,
          SUM(CASE WHEN sr_interval BETWEEN 8 AND 21 THEN 1 ELSE 0 END) as weeks3,
          SUM(CASE WHEN sr_interval > 21 THEN 1 ELSE 0 END) as long_term
        FROM study_progress WHERE user_id=?
    """, (u['id'],)).fetchone()

    intervals = dict(intervals) if intervals else {}
    conn.close()
    words_data = [dict(w) for w in due]
    return render_template('review.html', u=dict(u), words=words_data,
                           total_due=total_due, upcoming=upcoming, intervals=intervals)


@app.route('/api/sr_review', methods=['POST'])
@login_required
def sr_review():
    """Process a spaced repetition review answer"""
    data = request.json
    u = me()
    word_id = data['word_id']
    quality = int(data['quality'])  # 0-5

    conn = get_db()
    sp = conn.execute("SELECT * FROM study_progress WHERE user_id=? AND word_id=?",
                      (u['id'], word_id)).fetchone()

    if sp:
        ef = sp['ease_factor'] if sp['ease_factor'] else 2.5
        interval = sp['sr_interval'] if sp['sr_interval'] else 0
        reps = sp['repetitions'] if sp['repetitions'] else 0
        new_interval, new_ef, new_reps, next_review = sm2(ef, interval, reps, quality)
        status = 'mastered' if new_interval >= 21 else ('learning' if quality >= 3 else 'new')
        conn.execute("""
            UPDATE study_progress SET
                sr_interval=?, ease_factor=?, repetitions=?, next_review=?,
                status=?, last_studied=CURRENT_TIMESTAMP,
                correct_count=correct_count+?, wrong_count=wrong_count+?
            WHERE user_id=? AND word_id=?
        """, (new_interval, new_ef, new_reps, next_review.isoformat(),
              status, 1 if quality >= 3 else 0, 1 if quality < 3 else 0,
              u['id'], word_id))
    else:
        # New word - init
        ef = 2.5
        conn.execute("""
            INSERT INTO study_progress(user_id, word_id, deck_id, status, ease_factor, sr_interval, repetitions, next_review, last_studied)
            SELECT ?, ?, deck_id, 'new', 2.5, 0, 0, NULL, CURRENT_TIMESTAMP
            FROM words WHERE id=?
        """, (u['id'], word_id, word_id))

    xp = {5: 10, 4: 8, 3: 5, 2: 2, 1: 1, 0: 0}.get(quality, 0)
    conn.execute("UPDATE users SET xp=xp+? WHERE id=?", (xp, u['id']))
    conn.commit()
    update_study_log(u['id'], xp=xp, words=1)

    u2 = conn.execute("SELECT xp FROM users WHERE id=?", (u['id'],)).fetchone()
    conn.close()

    new_ach = check_achievements(u['id'])
    return jsonify({
        'ok': True,
        'new_interval': new_interval if sp else 1,
        'xp_earned': xp,
        'total_xp': u2['xp'],
        'new_achievements': new_ach
    })


@app.route('/api/sr_stats')
@login_required
def sr_stats():
    u = me()
    conn = get_db()
    # Forecast: how many reviews each day for next 7 days
    forecast = []
    for i in range(7):
        target = (datetime.now() + timedelta(days=i)).date().isoformat()
        count = conn.execute("""
            SELECT COUNT(*) FROM study_progress
            WHERE user_id=? AND date(next_review)=?
        """, (u['id'], target)).fetchone()[0]
        forecast.append({'date': target, 'count': count})
    conn.close()
    return jsonify({'forecast': forecast})


# ═══════════════════════════════════════════════════════════════
# AI CHATBOT (Gemini API + Pronunciation TTS)
# ═══════════════════════════════════════════════════════════════

GEMINI_DEFAULT_MODEL = 'gemini-2.5-flash'
GEMINI_DEFAULT_TTS_MODEL = 'gemini-2.5-flash-preview-tts'
GEMINI_DEFAULT_API_VERSION = 'v1beta'
GEMINI_DEFAULT_TTS_VOICE = 'Kore'


def clean_model_name(model_name, default_name):
    model_name = (model_name or '').strip() or default_name
    if model_name.startswith('models/'):
        model_name = model_name.split('/', 1)[1]
    return model_name


def get_gemini_config():
    load_env_file()
    return {
        'model': clean_model_name(os.getenv('GEMINI_MODEL', GEMINI_DEFAULT_MODEL), GEMINI_DEFAULT_MODEL),
        'api_key': os.getenv('GEMINI_API_KEY', '').strip(),
        'api_version': (os.getenv('GEMINI_API_VERSION', GEMINI_DEFAULT_API_VERSION).strip() or GEMINI_DEFAULT_API_VERSION),
        'tts_model': clean_model_name(os.getenv('GEMINI_TTS_MODEL', GEMINI_DEFAULT_TTS_MODEL), GEMINI_DEFAULT_TTS_MODEL),
        'tts_voice': (os.getenv('GEMINI_TTS_VOICE', GEMINI_DEFAULT_TTS_VOICE).strip() or GEMINI_DEFAULT_TTS_VOICE),
    }


def gemini_endpoint(model_name, api_version):
    return f"https://generativelanguage.googleapis.com/{api_version}/models/{clean_model_name(model_name, GEMINI_DEFAULT_MODEL)}:generateContent"


def call_gemini_generate_content(model_name, payload, api_key, api_version):
    import urllib.request

    data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
    req = urllib.request.Request(
        gemini_endpoint(model_name, api_version),
        data=data,
        headers={
            'Content-Type': 'application/json',
            'x-goog-api-key': api_key,
        },
        method='POST'
    )
    with urllib.request.urlopen(req, timeout=45) as resp:
        return json.loads(resp.read().decode('utf-8'))


def extract_gemini_text(result):
    for cand in result.get('candidates', []) or []:
        content = cand.get('content') or {}
        for part in content.get('parts', []) or []:
            if isinstance(part, dict) and part.get('text'):
                return part['text']
    return ''


def extract_gemini_inline_data_b64(result):
    for cand in result.get('candidates', []) or []:
        content = cand.get('content') or {}
        for part in content.get('parts', []) or []:
            inline_data = part.get('inlineData') or part.get('inline_data') or {}
            if inline_data.get('data'):
                return inline_data['data']
    return ''


def parse_json_loose(raw_text):
    raw_text = (raw_text or '').strip()
    if not raw_text:
        return {}
    if raw_text.startswith('```'):
        raw_text = re.sub(r'^```(?:json)?\s*', '', raw_text)
        raw_text = re.sub(r'\s*```$', '', raw_text)
    return json.loads(raw_text)


def normalize_chat_messages(messages):
    normalized = []
    for item in messages or []:
        role = 'model' if item.get('role') == 'assistant' else 'user'
        content = (item.get('content') or '').strip()
        if content:
            normalized.append({'role': role, 'parts': [{'text': content}]})
    return normalized or [{'role': 'user', 'parts': [{'text': 'Xin chào'}]}]


def chat_response_schema():
    return {
        'type': 'object',
        'properties': {
            'answer_markdown': {
                'type': 'string',
                'description': 'Cau tra loi bang Markdown ngan gon, huu ich va de doc. Phai viet bang dung ngon ngu ma nguoi dung yeu cau hoac ngon ngu ma cau hoi dang dung.'
            },
            'headword': {
                'type': 'string',
                'description': 'Tu hoac cum tu dang duoc giai thich/chuyen ngu. Co the la Anh, Han, Nhat hoac Viet. Neu khong ro thi de trong.'
            },
            'ipa': {
                'type': 'string',
                'description': 'Phien am IPA quoc te chinh xac cua headword. Uu tien IPA. Neu khong chac chan thi de trong.'
            },
            'romanization': {
                'type': 'string',
                'description': 'Phien am La-tinh hoac cach doc de hoc, vi du romaji cho tieng Nhat, revised romanization cho tieng Han. Neu khong can thi de trong.'
            },
            'native_script': {
                'type': 'string',
                'description': 'Dang viet bang chu ban dia cua tu/cum tu, vi du Hangul hoac Kanji/Kana. Neu khong can thi de trong.'
            },
            'pronunciation_text': {
                'type': 'string',
                'description': 'Text can doc thanh tieng, thuong la headword hoac native_script. Nen la van ban thuoc dung ngon ngu dich de TTS doc chuan.'
            },
            'example_sentence': {
                'type': 'string',
                'description': 'Mot cau vi du ngan thuoc ngon ngu dich hoac ngon ngu dang hoc, phu hop de doc mau. Neu khong co thi de trong.'
            },
            'language_code': {
                'type': 'string',
                'description': 'Ma ngon ngu BCP-47 de doc phat am, nhu en-US, ja-JP, ko-KR, fr-FR, vi-VN.'
            },
            'answer_language': {
                'type': 'string',
                'description': 'Ngon ngu dung de viet cau tra loi, vi du vi, en, ja, ko.'
            },
            'target_language': {
                'type': 'string',
                'description': 'Ngon ngu cua tu/cum tu dang duoc giai thich hoac dich toi, vi du en, ja, ko, vi.'
            }
        },
        'required': ['answer_markdown']
    }


def normalize_chat_payload(data):
    text_reply = (data.get('answer_markdown') or '').strip()
    if not text_reply:
        text_reply = 'Mình chưa nhận được nội dung hợp lệ từ Gemini. Bạn thử hỏi lại nhé.'

    headword = (data.get('headword') or '').strip()
    ipa = (data.get('ipa') or '').strip().strip('/')
    romanization = (data.get('romanization') or '').strip()
    native_script = (data.get('native_script') or '').strip()
    pronunciation_text = (data.get('pronunciation_text') or '').strip()
    example_sentence = (data.get('example_sentence') or '').strip()
    language_code = (data.get('language_code') or '').strip() or 'en-US'
    answer_language = (data.get('answer_language') or '').strip() or 'vi'
    target_language = (data.get('target_language') or '').strip() or ''

    if not pronunciation_text:
        pronunciation_text = native_script or headword
    if not headword and pronunciation_text:
        headword = pronunciation_text

    return {
        'reply': text_reply,
        'meta': {
            'headword': headword,
            'ipa': ipa,
            'romanization': romanization,
            'native_script': native_script,
            'text': pronunciation_text,
            'example_sentence': example_sentence,
            'language_code': language_code,
            'answer_language': answer_language,
            'target_language': target_language,
        }
    }


def pcm_b64_to_wav_b64(pcm_b64, rate=24000, channels=1, sample_width=2):
    pcm_bytes = base64.b64decode(pcm_b64)
    buf = io.BytesIO()
    with wave.open(buf, 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_bytes)
    return base64.b64encode(buf.getvalue()).decode('ascii')


@app.route('/chat')
@login_required
def chat():
    u = me()
    conn = get_db()
    my_decks = conn.execute("""
        SELECT d.* FROM decks d JOIN user_decks ud ON d.id=ud.deck_id AND ud.user_id=?
    """, (u['id'],)).fetchall()
    conn.close()
    cfg = get_gemini_config()
    return render_template(
        'chat.html',
        u=dict(u),
        my_decks=[dict(d) for d in my_decks],
        chat_model_label=cfg['model'],
        tts_voice=cfg['tts_voice'],
        gemini_ready=bool(cfg['api_key']),
    )


@app.route('/api/chat', methods=['POST'])
@login_required
def api_chat():
    import urllib.error

    cfg = get_gemini_config()
    data = request.json or {}
    messages = data.get('messages', [])
    deck_id = data.get('deck_id')
    u = me()
    user_msg = messages[-1]['content'] if messages else ''

    if not cfg['api_key']:
        fallback = fallback_chat_payload(user_msg, deck_id, reason='missing_key')
        return jsonify({
            'ok': True,
            'reply': fallback['reply'],
            'meta': fallback['meta'],
            'demo': True,
            'error_hint': 'Missing GEMINI_API_KEY'
        })

    vocab_context = ''
    if deck_id:
        conn = get_db()
        deck = conn.execute('SELECT * FROM decks WHERE id=?', (deck_id,)).fetchone()
        words = conn.execute("""
            SELECT w.word, w.meaning, w.pronunciation, w.example, sp.status
            FROM words w LEFT JOIN study_progress sp ON sp.word_id=w.id AND sp.user_id=?
            WHERE w.deck_id=? ORDER BY w.order_idx LIMIT 20
        """, (u['id'], deck_id)).fetchall()
        conn.close()
        if deck:
            vocab_context = f"\n\nNguoi dung dang hoc bo tu: '{deck['name']}'.\nDanh sach goi y:\n"
            for w in words[:15]:
                vocab_context += f"- {w['word']} [{w['pronunciation'] or ''}]: {w['meaning']}"
                if w['example']:
                    vocab_context += f" | VD: {w['example']}"
                vocab_context += '\n'

    system_prompt = f"""Ban la LexiBot Gemini - tro ly AI hoc ngoai ngu cua LexiVault Pro.

Pham vi ho tro uu tien:
- Tra cuu va giai thich tieng Anh, tieng Han, tieng Nhat.
- Dich mot tu/cum tu tu tieng Viet sang tieng Anh, Han hoac Nhat va nguoc lai.
- Dua phien am IPA quoc te chinh xac neu co the. Voi tieng Nhat/Han, co the bo sung romaji/romanization de nguoi hoc de doc.

Quy tac bat buoc:
- Nhan dien ngon ngu ma nguoi dung muon BAN TRA LOI, roi viet answer_markdown bang dung ngon ngu do.
  + Neu nguoi dung hoi bang tieng Viet va khong yeu cau khac: tra loi bang tieng Viet.
  + Neu nguoi dung yeu cau 'tra loi bang tieng Anh/Han/Nhat' thi phai theo dung ngon ngu yeu cau.
- Nhan dien ngon ngu dich/tra cuu cua tu dang hoc (target language).
- Neu nguoi dung dua ra mot tu tieng Viet va muon sang Anh/Han/Nhat, hay tra loi ban dich tu nhien nhat, kem chu viet goc, IPA neu co, romanization neu huu ich, va 1 cau vi du ngan.
- Neu nguoi dung hoi ve phat am, uu tien tra IPA chuan quoc te. Khong doan bua neu khong chac chan.
- Khi da xac dinh duoc tu/cum tu can doc, phai dien headword, ipa, pronunciation_text, language_code.
- Voi tieng Han/Nhat, neu co native script thi dien native_script; neu co cach doc La-tinh thi dien romanization.
- pronunciation_text nen la van ban ma TTS can doc chuan nhat. Thuong uu tien native_script cho ja/ko, va uu tien tu goc cho en.
- answer_markdown phai la noi dung hoan chinh de hien thi cho nguoi dung, ngan gon, ro rang, de hoc.

Huong dan trinh bay goi y:
- Neu la tra cuu tu vung: nghia/chuyen ngu + tu loai + IPA + vi du ngan.
- Neu la dich tu don: dua 1-3 ban dich tot nhat, note sac thai neu can.
- Neu la so sanh hoac giai thich: tra loi co cau truc ngan gon.

Nguoi dung hien tai: {u['username']}.{vocab_context}"""

    payload = {
        'systemInstruction': {'parts': [{'text': system_prompt}]},
        'contents': normalize_chat_messages(messages)[-20:],
        'generationConfig': {
            'temperature': 0.65,
            'maxOutputTokens': 1200,
            'responseMimeType': 'application/json',
            'responseJsonSchema': chat_response_schema(),
        }
    }

    try:
        result = call_gemini_generate_content(cfg['model'], payload, cfg['api_key'], cfg['api_version'])
        raw_text = extract_gemini_text(result)
        parsed = parse_json_loose(raw_text)
        normalized = normalize_chat_payload(parsed)
        return jsonify({
            'ok': True,
            'reply': normalized['reply'],
            'meta': normalized['meta'],
            'model': cfg['model'],
        })
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        reason = 'temporary_error'
        hint = f'Gemini error {e.code}'
        if e.code in (401, 403):
            reason = 'invalid_key'
            hint = 'Invalid Gemini API key'
        elif e.code == 429:
            reason = 'quota'
            hint = 'Gemini rate limit or quota exceeded'
        fallback = fallback_chat_payload(user_msg, deck_id, reason=reason)
        return jsonify({
            'ok': True,
            'reply': fallback['reply'],
            'meta': fallback['meta'],
            'demo': True,
            'error_hint': f"{hint}: {body[:160]}"
        })
    except Exception:
        fallback = fallback_chat_payload(user_msg, deck_id, reason='network_error')
        return jsonify({
            'ok': True,
            'reply': fallback['reply'],
            'meta': fallback['meta'],
            'demo': True,
            'error_hint': 'Network or upstream error'
        })


@app.route('/api/pronounce', methods=['POST'])
@login_required
def api_pronounce():
    import urllib.error

    payload_in = request.json or {}
    text_to_speak = (payload_in.get('text') or '').strip()
    ipa = (payload_in.get('ipa') or '').strip().strip('/')
    language_code = (payload_in.get('language') or payload_in.get('language_code') or 'en-US').strip() or 'en-US'

    if not text_to_speak:
        return jsonify({'ok': False, 'error': 'Missing text'}), 400

    cfg = get_gemini_config()
    if not cfg['api_key']:
        return jsonify({'ok': False, 'fallback': True, 'error': 'Missing GEMINI_API_KEY'}), 400

    guide_bits = [
        'You are a pronunciation coach for language learners.',
        'Generate clear single-speaker audio only.',
        'Speak the target text exactly as written, once, in a natural and careful style.',
    ]
    if language_code.startswith('en'):
        guide_bits.append('Use clear American English pronunciation.')
    elif language_code.startswith('ja'):
        guide_bits.append('Use clear Japanese pronunciation.')
    elif language_code.startswith('ko'):
        guide_bits.append('Use clear Korean pronunciation.')
    elif language_code.startswith('fr'):
        guide_bits.append('Use clear French pronunciation.')
    elif language_code.startswith('vi'):
        guide_bits.append('Use clear Vietnamese pronunciation.')
    if ipa:
        guide_bits.append(f'Pronunciation guide: /{ipa}/.')
    guide_bits.append(f'Target text: "{text_to_speak}"')
    tts_prompt = ' '.join(guide_bits)

    tts_payload = {
        'contents': [{'parts': [{'text': tts_prompt}]}],
        'generationConfig': {
            'responseModalities': ['AUDIO'],
            'speechConfig': {
                'voiceConfig': {
                    'prebuiltVoiceConfig': {
                        'voiceName': cfg['tts_voice']
                    }
                }
            }
        }
    }

    try:
        result = call_gemini_generate_content(cfg['tts_model'], tts_payload, cfg['api_key'], cfg['api_version'])
        pcm_b64 = extract_gemini_inline_data_b64(result)
        if not pcm_b64:
            return jsonify({'ok': False, 'fallback': True, 'error': 'No audio returned'}), 502
        wav_b64 = pcm_b64_to_wav_b64(pcm_b64)
        return jsonify({
            'ok': True,
            'audio_base64': wav_b64,
            'mime_type': 'audio/wav',
            'model': cfg['tts_model'],
            'voice': cfg['tts_voice'],
        })
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='ignore')
        return jsonify({
            'ok': False,
            'fallback': True,
            'error': f'Gemini TTS error {e.code}: {body[:160]}'
        }), 502
    except Exception:
        return jsonify({
            'ok': False,
            'fallback': True,
            'error': 'Gemini TTS network or upstream error'
        }), 502



def extract_focus_word(user_msg):
    text = (user_msg or '').strip()
    if not text:
        return ''

    quoted = re.findall(r'["\']([^"\']{2,60})["\']', text)
    if quoted:
        token = re.findall(r'[A-Za-z][A-Za-z-]*', quoted[0])
        return token[0].lower() if token else ''

    lowered = text.lower()
    for marker in ('từ ', 'tu ', 'word ', 'nghĩa của ', 'nghia cua ', 'giải thích ', 'giai thich ', 'pronounce ', 'phat am '):
        idx = lowered.find(marker)
        if idx >= 0:
            token = re.findall(r'[A-Za-z][A-Za-z-]*', text[idx + len(marker):])
            if token:
                return token[0].lower()

    tokens = re.findall(r'[A-Za-z][A-Za-z-]*', text)
    if len(tokens) == 1:
        return tokens[0].lower()
    return ''


def fallback_chat_payload(user_msg, deck_id=None, reason=''):
    local_payload = local_vocab_payload(user_msg, deck_id)
    if local_payload:
        if reason == 'quota':
            local_payload['reply'] = 'Gemini dang tam thoi vuot quota, LexiBot chuyen sang du lieu noi bo.\n\n' + local_payload['reply']
        elif reason in ('invalid_key', 'network_error', 'temporary_error'):
            local_payload['reply'] = 'Ket noi Gemini dang gap van de, LexiBot tam tra loi bang du lieu trong app.\n\n' + local_payload['reply']
        elif reason == 'missing_key':
            local_payload['reply'] = 'Demo mode - chua cau hinh GEMINI_API_KEY.\n\n' + local_payload['reply']
        return local_payload
    return demo_payload(user_msg, reason=reason)


def local_vocab_payload(user_msg, deck_id=None):
    focus_word = extract_focus_word(user_msg)
    if not focus_word:
        return None

    conn = get_db()
    params = [focus_word]
    sql = """
        SELECT w.word, w.pronunciation, w.meaning, w.example, w.example_vn, w.synonyms,
               w.part_of_speech, d.name AS deck_name
        FROM words w
        JOIN decks d ON d.id = w.deck_id
        WHERE lower(w.word) = ?
    """
    if deck_id:
        sql += ' AND w.deck_id = ?'
        params.append(deck_id)
    sql += ' ORDER BY w.deck_id LIMIT 1'
    row = conn.execute(sql, params).fetchone()
    if not row and deck_id:
        row = conn.execute("""
            SELECT w.word, w.pronunciation, w.meaning, w.example, w.example_vn, w.synonyms,
                   w.part_of_speech, d.name AS deck_name
            FROM words w
            JOIN decks d ON d.id = w.deck_id
            WHERE lower(w.word) = ?
            ORDER BY w.deck_id LIMIT 1
        """, (focus_word,)).fetchone()
    conn.close()

    if not row:
        return None

    parts = [
        f"**{row['word']}** /{row['pronunciation'] or '...'} /",
        f"**Loai tu:** {row['part_of_speech'] or 'word'}",
        f"**Nghia:** {row['meaning']}",
    ]
    if row['example']:
        parts.append(f"**Vi du:** {row['example']}")
    if row['example_vn']:
        parts.append(f"**Dich:** {row['example_vn']}")
    if row['synonyms']:
        parts.append(f"**Tu gan nghia:** {row['synonyms']}")
    parts.append(f"**Bo tu:** {row['deck_name']}")
    parts.append('Ban co the hoi tiep: dat cau, meo ghi nho, hoac phat am tu nay.')

    return {
        'reply': '\n\n'.join(parts),
        'meta': {
            'headword': row['word'],
            'ipa': row['pronunciation'] or '',
            'text': row['word'],
            'example_sentence': row['example'] or '',
            'language_code': 'en-US',
            'romanization': '',
            'native_script': '',
            'answer_language': 'vi',
            'target_language': 'en',
        }
    }


def demo_payload(user_msg, reason=''):
    msg = (user_msg or '').lower()
    prefix = ''
    if reason == 'quota':
        prefix = 'Gemini dang het quota nen LexiBot chuyen sang demo mode.\n\n'
    elif reason in ('invalid_key', 'network_error', 'temporary_error'):
        prefix = 'Ket noi Gemini dang gap van de nen LexiBot chuyen sang demo mode.\n\n'
    elif reason == 'missing_key':
        prefix = 'Demo mode - chua co Gemini API key.\n\n'

    is_greeting = bool(re.search(r'\b(hello|hi)\b', msg)) or 'xin chao' in msg or 'xin chào' in msg or msg.strip() in ('chao', 'chào')
    if is_greeting:
        return {
            'reply': prefix + 'Xin chao! Toi la **LexiBot Gemini** 🤖\n\nHay hoi toi ve bat ky tu tieng Anh nao. Toi co the giai thich nghia, IPA, vi du va cach phat am.\n\n*Luu y: de dung AI that va TTS that, hay cau hinh `GEMINI_API_KEY` truoc khi chay app.*',
            'meta': {'headword': '', 'ipa': '', 'text': '', 'example_sentence': '', 'language_code': 'en-US', 'romanization': '', 'native_script': '', 'answer_language': 'vi', 'target_language': ''}
        }
    if any(w in msg for w in ['colonel', 'pronounce', 'phat am', 'phiên âm', 'phien am']):
        return {
            'reply': prefix + "**colonel** /ˈkɝːnəl/\n\n**Nghia:** dai ta.\n\n**Meo phat am:** doc gan giong *kernel*, khong doc theo mat chu *co-lo-nel*.\n\n**Vi du:** *The colonel addressed the troops.*",
            'meta': {'headword': 'colonel', 'ipa': 'ˈkɝːnəl', 'text': 'colonel', 'example_sentence': 'The colonel addressed the troops.', 'language_code': 'en-US'}
        }
    if any(w in msg for w in ['ielts', 'toeic', 'toefl']):
        return {
            'reply': prefix + 'De hoc hieu qua cho ky thi, ban nen hoc theo chu de, on lap lai theo Spaced Repetition, va luyen nghe/phat am tung tu bang nut 🔊 trong app.',
            'meta': {'headword': '', 'ipa': '', 'text': '', 'example_sentence': '', 'language_code': 'en-US', 'romanization': '', 'native_script': '', 'answer_language': 'vi', 'target_language': ''}
        }
    return {
        'reply': prefix + f"**Demo mode**\n\nBan vua hoi: *\"{user_msg[:80]}\"*\n\nGemini hien chua kha dung trong cau hinh hien tai, nhung ban van co the tra cuu tu trong bo du lieu san co va dung nut 🔊 de nghe phat am co ban.",
        'meta': {'headword': '', 'ipa': '', 'text': '', 'example_sentence': '', 'language_code': 'en-US'}
    }

if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
