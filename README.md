# GündemRadar v2.1 — 6 saatlik Türkçe haber gündemi

Tek liste, minimal arayüz, otomatik yeni kişi keşfi ve görünür geri sayım. **İlk sürüm 0 TL hedefiyle** tasarlanmıştır. X/TikTok/Instagram paylaşımlarının tümünü ölçmez: kaynaklar Türkçe haberler ve Google Trends Türkiye RSS sinyalleridir. İddiası **ölçülebilir haber gündemi** olmalıdır; kusursuz sosyal medya popülerliği değildir.

## Yeni sürüm neleri değiştiriyor?

- **Tek sıralama:** Son 24 saatlik haber eşleşmesinin ağırlığı baskın. Hızlı artış en fazla **%20** ek etki, Google Trends başlığında eşleşme en fazla **%5** ek etki sağlar. Endeks puanı listenin lideri **100** olacak şekilde ölçeklenir.
- **Daha fazla isim:** `scripts/people.json` içinde 26 başlangıç kişisi var. Google Trends Türkiye başlıkları, Trends'e bağlı haber başlıkları ve mevcut liderlerin haberleri taranır. Yeni isim hipotezleri **Wikidata'da insan olduğu doğrulandığında** listeye eklenir. Yeni kişinin en az iki güncel haber eşleşmesi olmalıdır. Son güncellemelerde en az iki eşleşmesi olan keşfedilen kişiler daha sonra da bir süre izlenir.
- **6 saatte bir tarama:** GitHub Actions planı **Türkiye saatiyle 00.17, 06.17, 12.17, 18.17**. `workflow_dispatch` ile elle çalıştırma da mevcut. GitHub tam dakikayı garanti etmez; cron-job.org da GitHub'daki çalışma/yayın gecikmesini ortadan kaldırmaz.
- **Sayaç:** Site bir sonraki **planlanan** taramaya kalan süreyi saniye saniye gösterir. Ayrıca son **başarılı veri güncellemesi** ve gecikme uyarısı bulunur. Sayfa açık bırakıldığında her 60 saniyede bir yeni JSON kontrol edilir.
- **Açılır detaylar:** Ünlü ismine basınca en fazla üç kaynak bağlantısı ve son 10 başarılı taramaya dayalı küçük grafik açılır. Kanıt yoksa haber uydurulmaz.
- **Ücretsiz ve bağımsız:** Python standart kütüphanesi, GitHub Actions, Cloudflare Pages (alternatif GitHub Pages). Ücretli LLM API anahtarı veya veritabanı gerekmiyor.

## Kurulum

1. ZIP içeriğini **herkese açık** yeni bir GitHub deposuna yükle. `.github/workflows/update.yml` dosyası gizli klasörlerde olduğu için mutlaka yüklenmeli.
2. GitHub > **Actions** > **GundemRadar - 6 saatte bir guncelle** > **Run workflow** ile ilk gerçek veri taramasını başlat. `site/data/rankings.json` başarılı taramadan sonra güncellenir. Veriye erişim başarısızsa eski veri korunur.
3. Cloudflare Dashboard > **Workers & Pages** > **Pages** > **Import existing Git repository**: deponu seç; framework `None`, build command boş, output directory `site`, repo root kök klasör. Cloudflare sana ücretsiz `*.pages.dev` adresi verir.
4. `?demo=1` son ekinde yalnızca **uydurulmuş örnek verilerle tasarım** görünür. Normal adreste gerçek tarama yapılmadan sahte sıralama gösterilmez.

Bilgisayarında sadece tasarımı denemek:

```bash
python -m http.server 8000 --directory site
# http://localhost:8000/?demo=1
```

İnternet erişimi olan ortamda veri taraması:

```bash
python -m unittest discover -s tests -v
python scripts/collect.py --source auto
```

`--source auto` önce GDELT'e ulaşır. Ana tarama başarısız olursa **bütün isimler** için Google News RSS yedeğine geçer. Aynı sıralamada iki farklı kaynağın ham adetleri karıştırılmaz. Kaynağa erişilemezse eski veri korunur. Bütün kaynaklar kullanım koşulları ve oran sınırlamalarına tabidir. Google News RSS sonuçları kısıtlı olabilir; bu sayı **gerçek toplam haber sayısı değildir**.

## Wikidata User-Agent uyumluluğu (v2.1 düzeltmesi)

Wikimedia API taleplerinde **proje adı ve ulaşılabilir iletişim yolu** gerekli. Bu sürümde GitHub Actions ortamındaki `GITHUB_REPOSITORY` değeri otomatik alınarak `https://github.com/kullanici/depo` biçiminde `User-Agent` ve `Api-User-Agent` başlıklarına yazılır. GitHub'da depoyu yükledikten sonra iletişim bağlantısı kendiliğinden oluşur; kodda sabit veya uydurma adres yoktur.

Bilgisayardan çalıştırırken yeni kişi keşfini de kullanmak istiyorsan örneğin ortam değişkeni ayarla: `GUNDEMRADAR_CONTACT=https://github.com/kullanici/depo`. Kendi proje adresini veya iletişim e-postanı kullan. Hiçbiri tanımlı değilse **Wikidata kişi keşfi atlanır**, mevcut izleme listesiyle haber taraması çalışmaya devam eder.

GitHub depo geçmişini azaltmak için her altı saatte bir `force push` **önerilmez**. Proje güvenli ve izlenebilir normal commit geçmişini kullanır.

## Neden cron-job.org zorunlu değil?

GitHub planlı görevleri geciktirebilir veya atlayabilir; resmi dokümanlar bunu söylüyor. Harici cron-job.org HTTP isteğini planlı gönderebilir ama GitHub'ın job kuyruğuna, veri API'lerine ve Cloudflare dağıtımına hız garantisi vermez. Ayrıca GitHub Workflow Dispatch API üzerinden tetiklemek için harici serviste bir erişim anahtarı saklamak gerekir. Sıfır maliyetli ilk sürümde mevcut GitHub schedule ve görünür gecikme göstergesi daha basit ve güvenli.

## Sınırlamalar

- Google Trends RSS tüm popüler kişileri göstermez. Yeni isim keşfi **eksiksiz değildir**; yalnızca başlık ve kaynaklarda bulunan, Wikidata'da doğrulanabilen isimler yakalanır.
- Wikidata'da “insan” olmak bir kişinin mutlaka Türkiye'de ünlü olduğunu kanıtlamaz. İsim çakışmaları ve yanlış olumlu eşleşmeler kontrol edilmeli.
- Türkçe haberler ≠ sosyal medya gönderileri. Aynı olayın farklı sitelerde haber olması haberde görünürlüğü artırır.
- Grafik ilk güncellemede oluşmaz; en az iki başarılı tarama ister.
- GDELT, Google Trends, Wikidata ve Google News RSS servislerinde kota, API değişikliği veya erişim sorunu olursa bazı bilgiler eksik kalır; canlı dış ağ testi bu paket hazırlanırken yapılamamıştır.
- Public GitHub depolarında 60 gün boyunca depo etkinliği olmazsa schedule devre dışı kalabilir. GitHub Actions çalışma durumunu düzenli kontrol et.

## Dosyalar

- `scripts/collect.py`: veri toplama, keşif, endeks ve geçmiş
- `scripts/people.json`: başlangıçta 26 kişinin listesi
- `site/index.html`, `site/styles.css`, `site/app.js`: statik tek sayfa arayüzü
- `site/data/rankings.json`: son **gerçek** veri (ilk kurulumda boş)
- `.github/workflows/update.yml`: 6 saatlik otomatik çalışma
- `tests/test_collect.py`: kaynak parser, aday isim ve puanlama için birim testleri
