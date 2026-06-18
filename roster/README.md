# Çelebi Roster Planlama Sistemi

Bu proje, haftalık roster Excel dosyasını Streamlit üzerinde okuyup **Haftalık Servis Planlaması**, yoğunluk raporları, görev/grup dağılımı, roster düzenleme ve Excel export ekranları oluşturur.

## Özellikler

- Yönetici girişi ve planlamacı girişi
- Yönetici şifresi: `ayferberat32`
- Planlamacı girişinde şifre yoktur
- Planlamacı modunda `Employee Number / Sicil` hiçbir ekranda ve export dosyasında görünmez
- Roster düzenleme ekranında First Name ile arama
- Pazartesi–Pazar vardiya değişince `Total Working Time` otomatik hesaplanır
- Saat + servis yoğunluk raporu Pazartesi’den Pazar’a kronolojik sıralanır
- Excel export alma

## GitHub'a yükleme

1. GitHub'da yeni repository oluştur.
2. Bu klasördeki dosyaları repository içine yükle:
   - `app.py`
   - `requirements.txt`
   - `.streamlit/config.toml`
   - `assets/celebi_logo.svg`
   - `README.md`
3. Commit yap.

## Streamlit Cloud'da açma

1. https://share.streamlit.io/ adresine gir.
2. GitHub hesabınla giriş yap.
3. **New app** seç.
4. Repository olarak bu projeyi seç.
5. Main file path kısmına şunu yaz:

```text
app.py
```

6. Deploy butonuna bas.

## Streamlit Secrets önerisi

Kod içinde varsayılan yönetici şifresi çalışır. Fakat repository public olacaksa şifreyi GitHub’da görünür bırakmamak için Streamlit Cloud üzerinde **App settings > Secrets** bölümüne şunu ekle:

```toml
ADMIN_PASSWORD = "ayferberat32"
```

Daha sonra istersen `app.py` içindeki fallback şifreyi değiştirebilirsin.

## Beklenen roster formatı

Roster dosyasında sistem şu yapıyı bekler:

1. sütun: Sicil / Employee Number  
2. sütun: First Name  
3. sütun: Last Name  
4. sütun: Servis kodu / District  
5. sütun: Grup / Team or Employee Group  
6–12. sütunlar: Pazartesi–Pazar vardiya bilgileri  
Sonraki sütunlar: Total Working Time, Target Working Time, Off Day Count

Örnek vardiya hücresi:

```text
0800-1700 (CW) [08:00h ]
```

## Not

Streamlit Cloud üzerinde yüklenen Excel dosyaları kalıcı veritabanına yazılmaz. Uygulama yeniden başlarsa dosyayı tekrar yüklemen gerekebilir. Düzenlediğin rosterı kaybetmemek için export butonuyla Excel olarak indir.
