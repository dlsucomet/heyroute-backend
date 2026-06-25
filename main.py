from fastapi import FastAPI, Depends, HTTPException, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from database import get_db
from vad_utils import apply_vad_filter

app = FastAPI(title="HeyRoute API")

@app.get("/health")
async def health_check():
	return {"status": "online", "message": "The HeyRoute FastAPI server is running!"}

@app.get("/db-check")
async def db_check(db: AsyncSession = Depends(get_db)):
	try:
		await db.execute(text("SELECT 1"))
		return {"database_status": "connected", "message": "Successfully communicating with postgresql"}
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Database connection failed: {str(e)}")
	
@app.post("/api/voice/vad")
async def process_voice_activity(audio_file: UploadFile = File(...)):
	try:
		audio_bytes = await audio_file.read()

		clean_audio_bytes = apply_vad_filter(audio_bytes)

		# just to calculate how much noise was filtered out
		original_size = len(audio_bytes)
		clean_size = len(clean_audio_bytes)
		
		return {
			"filename": audio_file.filename,
			"original_bytes": original_size,
			"clean_bytes": clean_size,
			"message": "Audio processed through VAD filter successfully."
		}
	except Exception as e:
		raise HTTPException(status_code=500, detail=f"Error processing audio file: {str(e)}")