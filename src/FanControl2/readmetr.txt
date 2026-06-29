===========================================================
FanControl2 by joergm6                           Help V.2.7
Support forum: IHAD
Acknowledgments: diddsen, _marv_, DreamKK, Lukasz S.
                 Spaeleus(it), mimi74(fr), Bschaar(nl)
===========================================================

FanControl2 Eklentisi — Türkçe Açıklama
FanControl2, Dreambox/Enigma2 cihazlarında CPU fanını akıllıca yönetmek için yazılmış bir eklenti. Yazarı joergm6 (IHAD forumundan). Özetle: cihazının ısısına göre fanı daha sessiz veya daha hızlı çalıştırır, fan arızalarına karşı cihazı korur.

Ne işe yarar?
Cihazındaki en yüksek 2 sıcaklık sensörünün ortalamasına göre 3 pinli veya 4 pinli fanı kontrol eder. Ayar yavaş yapılır çünkü:

Sıcaklıklar zaten ani değişmez
Gereksiz CPU yükü oluşmasın


Güvenlik Özellikleri

20 dakika boyunca fandan hız bilgisi gelmezse "fan bozuk" kabul eder ve TV'de uyarı gösterir.
Standby modunda fan kapalıysa, maksimum sıcaklık aşılınca fan devreye girer. Sıcaklık 3°C düşünce fan tekrar kapanır. Açıldığında ilk 10 dakika minimum hızda çalışır.
Aşırı ısınma koruması +9°C'ye kadar artırılabilir.
Kritik sıcaklıkta veya fan arızasında cihazı otomatik kapatabilir.


Ana Ayarlar
Fan off in Standby (Beklemede fan kapalı)

yes: Cihaz standby'a geçince fan kapansın
yes, Except for recording or HDD: Kayıt yoksa ve HDD uykudaysa fan kapansın (en mantıklı seçim)

Hız parametreleri
AyarAnlamıMin Speed"Static temperature" ve altındaki sıcaklıklarda bu hızda dönerMax Speed"End temperature"a ulaşınca bu hızda dönerStatic temperatureBu sıcaklığa kadar fan minimum hızda döner, regülasyon yapılmazEnd Temperatureİzin verilen maksimum sıcaklık — fan bu noktada tam güçte döner
Initial Voltage / Initial PWM (Başlangıç Gerilimi / PWM)
Bu değerler değiştirildiğinde fan anında o ayara gider — böylece hızını doğrudan okuyabilirsin. Cihaz açılırken veya standby'dan çıkarken bu değerler kullanılır.

Fan Tipleri — En Kritik Bölüm
3Pin Fan

Sadece gerilim kontrol edilir. PWM ayarları bu modda işe yaramaz.
Başlangıç gerilimini, fan açılışta istediğin tur sayısına karşılık gelen değere ayarla.

4Pin Fan

Önce PWM değeri kontrol edilir.
PWM aralığı yetmezse gerilim de değiştirilir.
Gerilim ayarı önemli: DM500HD için 5-10 arası önerilir. Düşük gerilim = düşük max/min hız.
Bazı fanlar PWM=0'da bile çok hızlı dönebilir — böyle durumda gerilimi düşür.

4Pin (PID) — Lukasz S. tarafından eklenen gelişmiş mod
PI kontrolör (Proportional-Integral) kullanır: algoritma bir "hedef RPM" hesaplar, kontrolör gerçek RPM'i bu hedefe getirmeye çalışır.
Özellikler:

%1 deadband: Küçük dalgalanmalarda kontrolör müdahale etmez (gürültü filtresi).
PID Ctl Err: Yüzde olarak kontrolörün hatayı gösterir — neden hızlanmak/yavaşlamak istediğini anlamak için.
Önce PWM ile kontrol edilir (gerilim minimumda tutulur). PWM 255'i aşacak olursa gerilim devreye girer, PWM tekrar 255'in altına inerse gerilim minimuma döner.

PID modunda kurulum:

Initial Voltage + Initial PWM'i fanın istediğin minimum hızda döneceği değerlere ayarla
O hızı "min speed RPM" olarak gir
"max speed RPM" gerçekten ulaşılabilir bir değer olmalı — ulaşılamayacak değer verirsen kontrolör anormal davranır

Bilinen sorunlar:

PWM-VLT geçiş sınırında kararsızlık olabilir → Static Temp'i öyle ayarla ki normal koşullarda PWM 255'e ulaşmasın veya gerilim minimumun altına inmesin.
Static temp değiştirilirse entegratör sıfırlanır → fan önce minimuma düşer, sonra ayarlanır.

Control Disabled
Regülasyon kapalı. Fan son değerlerle çalışmaya devam eder, kapatılmaz.

Check (Kontrol) Özelliği
Fanın gerçek minimum başlama hızı ve minimum durma hızını tespit eder, aynı şekilde maksimum hızı da ölçer.

(OK) = ölçüm ayarlarla uyumlu
(!!) = ölçüm ayarlarla uyumsuz

Bu bilgiler sadece referans içindir, regülasyonu etkilemez. 4Pin modda ayrıca genişletilmiş kontrol aralığı bilgisi de gösterilir.

Temperature Monitor

Info tuşu → tek tek sıcaklık sensörlerinin değerlerini gösterir
Info tuşuna tekrar basmak → HDD sıcaklığını tek seferlik okur


Özel Ayarlar (Menu tuşu)
AyarVarsayılanAçıklamaAction in case of fan failureshow infoFan bozukluğunda: bilgi göster / cihazı kapat / hiçbir şey yapmaBox shutdown at temperature65°CBu sıcaklıkta DeepStandby'a geçerThermal protection increase0Standby'daki devreye girme sıcaklığını +9°C'ye kadar artırırread HDD-Temperature in StandbyautoHDD uykudayken sıcaklık okunsun mu? (auto = FC2 başlarken test eder)DMM fancontrol disabledNoDMM'in kendi fan kontrolünü devre dışı bırakır — öneri: etkinleştir, yoksa istenmeyen aç/kapa döngüleri olurShow Monitor in extension menuYesUzun mavi tuşa basınca monitör görünürWebIF number of log entries40Web arayüzünde gösterilecek olay sayısı (40-999)

Günlük Kaydı

Logging directory: Günlük dosyalarının yazılacağı klasör (en az 10MB boş alan olmalı)
Enable Data Logging: Her dakika FC2data.csv dosyasına kayıt. Excel'de doğrudan açılabilir. ~4kB/saat.
Auto-Delete Data older than (days): Belirtilen günden eski verileri günlük 00:00'da ve Enigma2 başlangıcında siler
Enable Event Logging: Tüm olaylar FC2events.txt dosyasına yazılır. ~30kB/saat


Web Arayüzü
Adres: http://dreambox-ip/fancontrol

Mevcut fan değerleri ve son olaylar görünür
FC2 Log: Günlük dosyalarını indir, günlük ayarlarını yap
FC2 Chart: Son 48 saatin grafikleri (en az 2.5 saatlik veri ve Data Logging açık olmalı)


Not: Firefox'ta grafik düzgün görünmezse sayfayı yenile (F5).


Genel

Tüm değerler hem sayı hem çubuk grafik olarak gösterilir.
Ayarlar Enigma2'nin normal ayarlarıyla saklanır → backup/restore'a otomatik dahil olur.
Eklenti çok dilli destekler, .pot dosyası pakette geliyor (seninle az önce Türkçe çevirisini yaptık zaten).


Senin için pratik öneriler
Donanımın Dreambox Two / DM920 olduğunu biliyorum. Önerilerim:

Fan type: Muhtemelen 4Pin — 4Pin (PID) modunu dene, en akıllı regülasyonu yapar.
Fan off in Standby: "yes, Except for recording or HDD" — kayıt varken fanı kapatmamak önemli.
Box shutdown temperature: 65°C güvenli varsayılan. Daha muhafazakar istiyorsan 60°C yap.
DMM fancontrol disabled: Yes — DM920'de DMM'in kendi fan kontrolü zaten var, çakışma olmasın.
Data Logging aç, bir süre veri topla, FC2 Chart ile cihazının termal profilini gör.

Önerilen Ayarlar
Şunları dene:

Boşta modunda fan kapalı:	yes, Except for Recording or HDD (kayıt varsa fan dursun istemezsin)
min Hız rpm:	1000 (gerçekçi başlangıç)
maks Hız rpm:	1800-2000 (70 Hz fanlar bunu çıkarır)
Sabit sıcaklık C:	50 (cihazın idle sıcaklığının biraz üstü)
Bitiş sıcaklığı C:	65 (15°C aralık)
Başlangıç Gerilimi:	80-100 (fanı döndürmeye yetecek minimum)
Başlangıç PWM:	50
