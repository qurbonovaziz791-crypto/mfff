import asyncio
import os
import logging
from pathlib import Path
from typing import Any, Optional

import aiohttp
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramNetworkError

def _load_dotenv(path: Path) -> None:
    try:
        if not path.exists():
            return
        for raw in path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        return


# `.env` dan tokenlarni yuklaymiz (terminalga kiritish shart bo'lmasin).
BASE_DIR = Path(__file__).resolve().parent
_load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = (os.environ.get("BOT_TOKEN", "") or "").strip()
API_BEARER_TOKEN = (os.environ.get("API_BEARER_TOKEN", "") or "").strip()

API_BASE_URL = (os.environ.get("API_BASE_URL", "http://127.0.0.1:8000") or "").strip().rstrip("/")

API_REGISTER = f"{API_BASE_URL}/api/bot/register/"
API_CHANGE = f"{API_BASE_URL}/api/bot/change-credentials/"

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. `.env` faylga BOT_TOKEN qo‘ying (namuna: .env.example).")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# States
class ChangeStates(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()

def _auth_headers() -> dict[str, str]:
    if not API_BEARER_TOKEN:
        return {}
    return {"Authorization": f"Bearer {API_BEARER_TOKEN}"}


async def send_to_api(session: aiohttp.ClientSession, url: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
    try:
        async with session.post(url, json=data, headers=_auth_headers()) as response:
            if response.status == 200:
                return await response.json()
            # 401/403 bo'lsa odatda bearer token sozlanmagan/noto'g'ri,
            # 5xx bo'lsa Django tomonda xato.
            try:
                body = await response.text()
            except Exception:
                body = ""
            print(f"API error: {response.status} {url} body={body[:400]!r}")
            return None
    except Exception as e:
        print(f"Xatolik API ulanishda: {e}")
        return None

def phone_keyboard() -> types.ReplyKeyboardMarkup:
    return types.ReplyKeyboardMarkup(
        keyboard=[
            [
                types.KeyboardButton(
                    text="Telefon raqamni yuborish", request_contact=True
                )
            ]
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
        selective=True,
    )

def remove_keyboard() -> types.ReplyKeyboardRemove:
    return types.ReplyKeyboardRemove()


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    text = (
        "Assalomu alaykum! <b>MYFEEL</b> ijtimoiy tarmog'iga xush kelibsiz.\n\n"
        "Ro'yxatdan o'tishni yakunlash uchun telefon raqamingizni yuborasiz.\n"
        "Telefon raqamingiz faqat akkauntni bog'lash va tiklash uchun kerak bo'ladi."
    )
    await message.answer(text, parse_mode="HTML", reply_markup=phone_keyboard())


@dp.message(F.contact)
async def on_contact(message: types.Message):
    # Faqat user o'zi yuborgan contactni qabul qilamiz
    if not message.contact or message.contact.user_id != message.from_user.id:
        await message.answer("Iltimos, tugma orqali o'zingizning telefon raqamingizni ulashing.", reply_markup=phone_keyboard())
        return

    phone = message.contact.phone_number
    await message.answer("Akkauntingiz ulanmoqda...", reply_markup=remove_keyboard())

    data = {
        "telegram_id": str(message.from_user.id),
        "phone": phone,
        "first_name": message.from_user.first_name,
        "last_name": message.from_user.last_name or "",
    }
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=float(os.environ.get("BOT_HTTP_TIMEOUT", "10")))
    ) as session:
        result = await send_to_api(session, API_REGISTER, data)

    if result and result.get("status") == "success":
        login = result.get("login")
        password = result.get("password")
        link = result.get("login_link")

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Profilimga kirish", url=link)]]
        )
        hidden_pwd = "*******" if password == "hidden" else password

        msg = (
            "<b>Muvaffaqiyatli ulandingiz!</b>\n\n"
            f"Login: <code>{login}</code>\n"
            f"Parol: <tg-spoiler>{hidden_pwd}</tg-spoiler>\n\n"
            "<i>/change_login yoki /change_password orqali ma'lumotlarni almashtirishingiz mumkin.</i>"
        )
        await message.answer(msg, reply_markup=keyboard, parse_mode="HTML")
    else:
        await message.answer(
            "Kechirasiz, ro'yxatdan o'tishda xatolik. Django API ishlayotganiga ishonch hosil qiling.\n\n"
            f"Tekshirish: API_BASE_URL={API_BASE_URL}\n"
            "Agar siz `scripts/start-prod.ps1` bilan server ko'targan bo'lsangiz, odatda port 8001 bo'ladi.\n"
            "Shunda `.env`da `API_BASE_URL=http://127.0.0.1:8001` qilib qo'ying.\n"
            "Agar `API_BEARER_TOKEN` yoqilgan bo'lsa, bot va Django `.env`da bir xil bo'lishi kerak.",
            reply_markup=phone_keyboard(),
        )

# --- Login O'zgartirish ---
@dp.message(Command("change_login"))
async def start_change_login(message: types.Message, state: FSMContext):
    await message.answer("Yangi foydalanuvchi nomini (loginingizni) kiriting (masalan: <i>shoxruz99</i>):", parse_mode="HTML")
    await state.set_state(ChangeStates.waiting_for_login)

@dp.message(ChangeStates.waiting_for_login)
async def process_new_login(message: types.Message, state: FSMContext):
    new_login = message.text.strip().lower().replace(" ", "_")
    
    data = {"telegram_id": str(message.from_user.id), "new_username": new_login, "new_password": None}
    
    msg = await message.answer("O'zgartirilmoqda tugatilmoqda...")
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=float(os.environ.get("BOT_HTTP_TIMEOUT", "10")))
    ) as session:
        result = await send_to_api(session, API_CHANGE, data)
    
    if result and result.get("status") == "success":
        link = result.get('login_link')
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Profilimga kirish 🚀", url=link)]])
        await msg.edit_text(f"✅ Loginingiz muvaffaqiyatli <code>{result.get('login')}</code> nomiga o'zgardi!", parse_mode="HTML", reply_markup=keyboard)
    else:
        await msg.edit_text("Xatolik! Balki bu login banddir yoxud tizim xatosi.")
    await state.clear()

# --- Parol O'zgartirish ---
@dp.message(Command("change_password"))
async def start_change_password(message: types.Message, state: FSMContext):
    await message.answer("Yangi maxfiy so'zni (parolni) kiriting (kamida 6 ta belgi):")
    await state.set_state(ChangeStates.waiting_for_password)

@dp.message(ChangeStates.waiting_for_password)
async def process_new_password(message: types.Message, state: FSMContext):
    if len(message.text) < 6:
        await message.answer("Parol juda qisqa, iltimos kamida 6 ta belgi yozing:")
        return
        
    new_password = message.text
    
    data = {"telegram_id": str(message.from_user.id), "new_username": None, "new_password": new_password}
    msg = await message.answer("Parol himoyalanmoqda...")
    async with aiohttp.ClientSession(
        timeout=aiohttp.ClientTimeout(total=float(os.environ.get("BOT_HTTP_TIMEOUT", "10")))
    ) as session:
        result = await send_to_api(session, API_CHANGE, data)
    
    if result and result.get("status") == "success":
        link = result.get('login_link')
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Tizimga kirish 🚀", url=link)]])
        await msg.edit_text("✅ Parolingiz muvaffaqiyatli o'zgartirildi!\nBoshqalar bilan bunday ma'lumotni ulashmang.", reply_markup=keyboard)
    else:
        await msg.edit_text("Xatolik! Tizimga ulanishda imkoni bo'lmadi.")
    await state.clear()

async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    print("MYFEEL Registration Telegram Bot ishga tushdi...")

    # Windows/ISP/proxy sabab api.telegram.org vaqti-vaqti bilan ishlamasligi mumkin.
    # Bot "jim" bo'lib qolmasin: network xatoda retry qilamiz.
    retry_s = float(os.environ.get("BOT_TELEGRAM_RETRY_SECONDS", "5"))
    while True:
        try:
            # Agar botda webhook qolgan bo'lsa, polling update olmay qolishi mumkin.
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot)
            return
        except (TelegramNetworkError, aiohttp.ClientConnectorError, OSError) as e:
            logging.error("Telegram ulanish xatosi: %s. %ss dan keyin qayta uriniladi.", e, retry_s)
            try:
                await bot.session.close()
            except Exception:
                pass
            await asyncio.sleep(retry_s)
            # aiogram sessiya yopilgach, Bot sessionini qayta ochadi (lazy) — davom etamiz.
            continue

if __name__ == "__main__":
    asyncio.run(main())
