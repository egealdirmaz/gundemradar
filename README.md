# GündemRadar — 50 Türk kişiyle kapalı liste testi

Bu sürümde yalnızca `scripts/people.json` içindeki **50 seçilmiş Türk tanınmış kişi** sıralanır. Yabancı ünlülerin, kurgusal karakterlerin ve Wikidata/Google Trends'ten otomatik keşfedilen yeni kişilerin listeye eklenmesi **kapatıldı**. Geçmiş veri dosyasındaki keşfedilmiş isimler yeni çalışmada geri alınmaz.

- Günde dört tarama: Türkiye saatiyle yaklaşık 00.17, 06.17, 12.17, 18.17. GitHub zamanlaması gecikebilir; sayaç planlanan zamanı gösterir.
- Tek liste, önceki 24 saate göre sınırlı ivme etkisi, kaynak bağlantıları.
- Kaynaklar GDELT / Google News RSS; bu **Türkiye genelinde sosyal medyada en çok konuşulan kişi** ölçümü değil, **bu 50 kişinin Türkçe haberlerdeki görünürlüğüne göre** bir denemedir.
- Listelenen kişi için 0 eşleşme çıkabilir. Bu bir hata değildir; kaynakların sınırlamalarını gösterir.
- Repo içindeki dosyalar ve kurallar eski ZIP ile aynıdır, değişen dosyalar: `scripts/people.json`, `scripts/collect.py`, `site/index.html`, `tests/test_collect.py`, `README.md`.

## GitHub'da uygulanması

1. Değişen dosyaları doğru klasörlerine yükleyerek mevcut dosyaların üzerine yaz. **`site/data/rankings.json` dosyasını elle sıfırlama.**
2. `Actions` → `GundemRadar - 6 saatte bir guncelle` → `Run workflow` çalıştır.
3. `site/data/rankings.json` dosyasında `rosterMode: fixed_50_turkish_people`, `rosterSize: 50` ve tam 50 `items` olması gerekir.
4. İsimler yalnızca `scripts/people.json` üzerinden değiştirilebilir; test kodu tam 50 benzersiz isim bekler.

## Doğrulama

```bash
python -m unittest discover -s tests -v
python scripts/collect.py --source auto
```

Başka bir kaynak için önce tüm 50 kişiye aynı kaynakla uygulayıp sıralamayı karşılaştırın. Kaynak sayıları tüm haberlerin kesin sayımı değildir.

Not: Sahne adıyla tanınan Hadise, Tarkan ve Sefo, haber eşleşmelerini kaçırmamak amacıyla kamusal sahne adlarıyla listelenir. Bunlar ilk pilotta uygunluk açısından önceden seçilmiş kişilerdir; popülerlik sırası gerçek veriye göre çıkar. İlk çalıştırma eski listenin sıralama geçmişini yeni 50 kişilik listeyle karşılaştırmaz.
