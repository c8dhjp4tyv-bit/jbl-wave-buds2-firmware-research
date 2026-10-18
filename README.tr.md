# JBL Wave Buds 2 — firmware ve OTA tersine mühendisliği

[![Tests](https://github.com/c8dhjp4tyv-bit/jbl-wave-buds2-firmware-research/actions/workflows/tests.yml/badge.svg)](https://github.com/c8dhjp4tyv-bit/jbl-wave-buds2-firmware-research/actions/workflows/tests.yml)

JBL Wave Buds 2 (Bestechnic **BES1306**, PID `2100`) için tersine mühendislik
notları ve tekrar üretilebilir araçlar: flash yerleşimi, OTA container formatının
byte-byte çözümü, BLE/GATT komut protokolü ve BES "TOTA v2" şifreli taşıması,
cihaz ve uygulama tarafındaki güven sınırları, fabrika konsolu, ve sahibi olduğun
bir cihaza kendi ürettiğin imajı yükleme yönteminin tekrar üretilebilir anlatımı.

Analiz iki yapıyı kapsar — IDA'da incelenen `wavebuds.elf` (Nisan 2025) ve dağıtım
paketi `2.9.0` (Eylül 2026) —, byte-byte eşlenen (identik repack ile doğrulanmış)
8 akışlı OTA container'ı, hem uygulama hem cihaz tarafında doğrulanmış CRC-32
bütünlük modeli, 54/59 girişli fabrika komut tablosu, 12 OTA RAM durum değişkeni,
7.960 fonksiyonluk envanter ve iki yapı arasındaki farkları içerir. Anlamsal
çözüm OTA/flash/CRC/fabrika altsistemlerinde derin, geri kalanında yalnızca
sayımdır — bkz. [eksiksizlik denetimi](docs/COMPLETENESS_AUDIT.md).

> [!WARNING]
> Bu, sahibi tarafından yapılan bir donanım araştırmasıdır; resmî bir JBL
> güncellemesi değildir. Değiştirilmiş imaj yüklemek geri dönüşsüzdür: indirme
> fazı staged ve brick'e dayanıklıdır, ama CRC-geçerli ama bozuk bir imajın
> aktivasyonunun **açık bir kurtarma yolu yoktur**. Bir şeyi tekrar üretmeden önce
> [SAFETY.md](SAFETY.md) dosyasını oku.

English version: [README.md](README.md)

![Test edilen JBL Wave Buds 2 uygulamada: iki kulaklık da bağlı ve %100, tüm kontroller çalışıyor](docs/images/device-after-flash.png)

*Test edilen ünitedeki donanım sonucu: uygulama + kullanıcı-CA MITM OTA hattı
doğrulandıktan sonra iki kulaklık da bağlanıyor, %100 gösteriyor ve tüm uygulama
kontrolleri (ANC/Ambient, hareketler, EQ) çalışıyor. Tek baytlık değiştirilmiş
imaj da aynı yolla kabul edildi ve cihaz tamamen işlevsel kaldı.*

## Doğrulanmış bulgular

Adresler incelenen yapıdandır (`wavebuds.elf`); bkz.
[adres defteri](docs/ADDRESS_LEDGER.md) ve [köken](docs/PROVENANCE.md).

- OTA imajı **kriptografik olarak imzalı değildir**. Cihaz tarafı bütünlük yalnız
  CRC-32'dir — handler `0x2C0918BC` config'i, her segmenti ve tüm imajı CRC-32
  rutini `0x2C0CE944` (tablo `0x2C0F5218`) ve bir `"BEST"` magic'iyle kontrol eder.
  CRC-geçerli, tek baytı değiştirilmiş bir imaj kabul edildi ve boot etti.
- Uygulamadaki RSA-2048 doğrulayıcı (`com.jbl.counterfeit.Rsa2048DynamicVerifier`)
  **anti-counterfeit** (cihaz gerçekliği) içindir, firmware imzası değil.
- Test edilen **değiştirilmiş uygulama** OTA akışında pinning yerel proxy'yi
  engellemedi. Orijinal uygulama yalnızca sistem CA'larına güvenir; kullanıcı
  CA'sı için sahibinin uygulama güven yapılandırmasını değiştirmesi gerekir.
- OTA **staged**: yeni imaj `0x28120000` adresine yazılır, çalışan uygulama
  korunur. Bu aktarım sırasındaki riski azaltır; garantili kurtarma sağlamaz.
- Harici bir BLE central OTA'yı **süremez**: handler'lar cihaz içi TWS/bağlantı
  durumuna bağlıdır (`0x2C0905E4`: `MEMORY[0x20026BA0] ∈ {2,4}`).
- BES **TOTA v2** taşıması AES-128 oturum anahtarını tamamen istemci tarafında
  türetir; sunucu/cihaz sırrı yoktur.
- Bir **fabrika/mühendislik konsolu** (incelenen yapıda 59, 2.9.0'da 54 komut)
  cihaz kimliği (MAC/BLE adresi), kristal trim ve BT link key okuyabilir/yazabilir.
  Kablosuz (over-the-air) erişilebilirliği `UNRESOLVED`.
- İki yapı **ayrı derlenmiş ve yeniden konumlanmıştır**: aynı ürün, kaymış
  adresler, 59 → 54 fabrika girişi. Bkz. [fark analizi](docs/PROVENANCE.md).

## Test edilen değişiklik

Değişiklik bilinçli olarak minimaldir — decompile imajın tek baytı. RTX çekirdek
metnini `RTX V5.5.1` → `V5.5.2` yapar (decompile offset `64096`) ve container
CRC-32 yeniden hesaplanır. Tasarım gereği kozmetiktir: amaç, cihazın CRC-geçerli
değiştirilmiş bir imajı kabul ettiğini kanıtlamaktır, davranış değiştirmek değil.

```text
Temel (sahip tarafından verilir; dağıtılmaz)
  resmî 2.9.0 paketi    549.558 bayt   SHA-256 836cb251f9fb2261dde14f39ba18d358c48018817f3c3d1b527e1ac5f3ab7ba2
  decompile imaj        955.596 bayt   SHA-256 489663e80b76f20f4c94671064908569fac5f4e3df10ab6d7369baffe094f67d
  container CRC-32       A0C7CCEC (geçerli), aralık [0x0, 0x862AD)
```

Depo bilerek **hiçbir JBL firmware'i içermez**. Kendi yasal paketini ver ve tekrar
üret:

```bash
python3 tools/ota_unpack.py  <resmi_2.9.0_paketi.bin> --extract image.bin
python3 tools/ota_repack.py  make-test <resmi_2.9.0_paketi.bin> test.bin
python3 tools/ota_unpack.py  test.bin      # decompile'da tam olarak tek bayt farklı; CRC geçerli
```

Yeniden paketlenen container'ın tam baytları LZMA kodlayıcıya bağlıdır; cihaz
**CRC-32'yi doğrular, paket hash'ini değil** (bkz. [docs/04](docs/04-security-model.md)),
ve decompile tek-bayt farkı deterministiktir. Uygulama üzerinden gönderim:
[docs/08](docs/08-delivery-method.md).

## Diyagramlar

| | |
|---|---|
| [Flash haritası](docs/images/flash-map.svg) | 2 MB NOR bölümlemesi |
| [OTA komut akışı](docs/images/ota-flow.svg) | dizi ve CRC-32 kontrol noktaları |
| [Güven sınırları](docs/images/trust-boundaries.svg) | her aşama neyi doğrular, imaj güveni nerede |

## Dokümantasyon

- [00 — Genel bakış](docs/00-overview.md)
- [01 — Donanım & flash haritası](docs/01-hardware-flash-map.md)
- [02 — OTA container formatı](docs/02-ota-container-format.md)
- [03 — Firmware image yerleşimi](docs/03-firmware-image-layout.md)
- [04 — Güvenlik modeli](docs/04-security-model.md)
- [05 — BLE/GATT & komutlar](docs/05-ble-gatt-and-commands.md)
- [06 — OTA protokolü](docs/06-ota-protocol.md)
- [07 — Uygulama tarafı analiz](docs/07-app-side-analysis.md)
- [08 — Gönderim yöntemi](docs/08-delivery-method.md)
- [09 — Fonksiyon kataloğu](docs/09-function-catalog.md)
- [10 — Fabrika konsolu](docs/10-factory-console.md)
- [Köken (iki yapı, kanıt sınıfları)](docs/PROVENANCE.md) · [Adres defteri](docs/ADDRESS_LEDGER.md)
- [Eksiksizlik denetimi](docs/COMPLETENESS_AUDIT.md) · [Kapsam & sınırlar](docs/COVERAGE_AND_LIMITATIONS.md)
- [Durum makineleri](docs/STATE_MACHINES.md) · [Olay günlüğü](docs/INCIDENTS.md)
- [Araçlar & kapsam](docs/TOOLS.md) · [Test & tekrar üretilebilirlik](docs/VALIDATION.md)
- [Üretilen kataloglar](docs/generated/README.md) · [IDA komut günlüğü](analysis/IDA_MCP_COMMAND_LOG.md)

## Bu proje neyi iddia ETMEZ

- JBL firmware'ini, uygulamayı (orijinal veya değiştirilmiş) veya kullanıma hazır
  özel imajı dağıtmaz.
- Belgelenen derleme aracı anti-counterfeit doğrulamasına dokunmaz.
- ROM bootloader'ın secure boot'tan yoksun olduğunu kanıtlamaz — o bölge her OTA
  imajının dışındadır ve dökülmedi; iddia statik kanıt + tek ünitede gözlemlenen
  değiştirilmiş-imaj boot'uyla sınırlandırılmıştır.
- Fabrika konsolunun over-the-air erişilebilir olduğunu iddia etmez.
- Hiçbir sonucun başka bir ünite, bölge veya firmware yapısı için geçerli olduğunu
  iddia etmez.

## Katkı, güvenlik ve atıf

Katkılar yapı kökenini korumalı ve firmware içermemelidir; bkz.
[CONTRIBUTING.md](CONTRIBUTING.md) ve [SAFETY.md](SAFETY.md). Güvenlikle ilgili
bulgular [SECURITY.md](SECURITY.md) izler. Atıf meta verisi
[CITATION.cff](CITATION.cff) içindedir; kullandığın tam commit veya etiketi belirt.

## Lisans

Betikler [MIT](LICENSE); dokümantasyon CC-BY-4.0. JBL/Harman firmware'i, ticari
markalar ve uygulama varlıkları sahiplerine aittir ve burada dağıtılmaz.
