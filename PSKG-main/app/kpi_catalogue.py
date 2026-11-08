"""Official PSKG 2026–2030 KPI catalogue.

Source: PSKG_final_KPI.pptx
  * Slide 9  – framework: 5 Teras, 10 Objektif Strategik, 20 Inisiatif Strategik (codes)
  * Slides 12/16/20/24/28 – initiative descriptions (takrif)
  * Slides 14/18/22/26/30 – "Sasaran Keberhasilan 2030", "Mekanisma Pengukuran",
    annual targets 2026–2030 and "Tanggungjawab/Pemilik Data"
  * Slide 33 – summary of 2030 targets (incl. "skor 4-5" for the Employer Satisfaction Index
    and "25 produk" cumulative for IP registrations)
  * Slides 37/38 – governance (IPT collects & validates, KPT secretariat checks consistency)

Numerator/denominator labels are transcribed VERBATIM from the "Mekanisma Pengukuran"
column. Nothing is substituted. Ambiguities are listed in `confirmation_notes` and in
docs/PENGESAHAN_KPT.md for confirmation by Dr Bibi / KPT. All formulas remain `draft`
until KPT formally adopts a KPI dictionary.
"""
from __future__ import annotations

TERAS = {
    1: "Bakat Global dan Progresif",
    2: "Pendidikan Berteraskan Kemahiran",
    3: "Pencipta Inovatif",
    4: "Sinergi Industri-Akademia",
    5: "Tanggungjawab dan Pembinaan Negara",
}

OBJEKTIF = {
    "T1/OS1": "Pembinaan Karakter",
    "T1/OS2": "Komunikasi Inklusif",
    "T1/OS3": "Minda ke Hadapan",
    "T2/OS1": "Kemahiran Kerja Sebenar",
    "T2/OS2": "Kemahiran Boleh Pindah",
    "T3/OS1": "Graduan Inovatif",
    "T3/OS2": "Graduan Usahawan",
    "T4/OS1": "Cipta Sama Bakat",
    "T4/OS2": "Pemerkasaan Hubungan",
    "T5/OS1": "Pemangkin Warga Bertanggungjawab",
}

GEN_NOTE = ("Takrif operasi (skop populasi, tarikh potong, kohort, kaedah kiraan berulang) "
            "belum diperakukan secara rasmi.")


def _t(*vals):
    return [{"value": v, "kind": "value", "label": None} for v in vals]


# fmt: off
KPI_CATALOGUE = [
    dict(id=1, code="T1/OS1/A", teras=1, title="Pengalaman Global (CBGE)",
         indicator="Pelajar mengikuti program Character Building Global Experience (CBGE)",
         definition="Program CBGE menyasarkan setiap pelajar mendapat sekurang-kurangnya satu pengalaman global sepanjang tempoh pengajian (1 Pelajar : 1 Pengalaman Global) melalui mobiliti fizikal, pertukaran maya, program hibrid, penempatan industri antarabangsa atau kolaborasi akademik rentas negara.",
         outcome_2030="Pengukuhan pembinaan karakter global dan kesiapsiagaan pelajar terhadap keperluan pasaran kerja masa hadapan. 10% pelajar mengikuti program CBGE.",
         numerator_label="Bilangan Pelajar Mengikut CBGE", denominator_label="Jumlah Enrolmen Pelajar",
         unit="percent", aggregation="pooled_ratio", subset_ratio=True,
         data_owner="BPPT, JPT | BKTVET, JPPKK | Pusat Antarabangsa, Fakulti, Pusat Kerjaya",
         targets=_t(2, 4, 6, 8, 10), source_ref="Slaid 12, 13, 14",
         confirmation_notes=["Sama ada pelajar dikira sekali sepanjang pengajian atau setiap tahun penyertaan (aspirasi '1 Pelajar : 1 Pengalaman Global')."]),
    dict(id=2, code="T1/OS2/A", teras=1, title="Bahasa Ketiga",
         indicator="Pendaftaran Bahasa Ketiga semasa pengajian",
         definition="Penguasaan bahasa tambahan selain Bahasa Melayu dan Bahasa Inggeris diperkasa sebagai kelebihan kompetitif graduan.",
         outcome_2030="Peningkatan maklum balas majikan terhadap keupayaan bahasa ketiga pelajar. 25% graduan mendaftar bahasa ketiga semasa dalam pengajian.",
         numerator_label="Bilangan Graduan Mendaftar Bahasa Ketiga", denominator_label="Jumlah Graduan",
         unit="percent", aggregation="pooled_ratio", subset_ratio=True,
         data_owner="BKA, JPT | BK, JPPKK | Bahagian Akademik, Pusat Bahasa, Fakulti",
         targets=_t(5, 10, 15, 20, 25), source_ref="Slaid 12, 13, 14",
         confirmation_notes=["Takrif kohort 'Jumlah Graduan' (graduan bergraduat pada tahun pelaporan?)."]),
    dict(id=3, code="T1/OS2/B", teras=1, title="Online/Virtual Global Classroom",
         indicator="Program Online/Virtual Global Classroom (OGC)",
         definition="Pengalaman pembelajaran rentas negara secara maya atau hibrid diperluas supaya lebih ramai pelajar berinteraksi dengan rakan antarabangsa tanpa bergantung sepenuhnya kepada mobiliti fizikal.",
         outcome_2030="Peningkatan penyertaan pelajar dalam program online global classroom (OGC) melalui kerjasama digital serantau. 10% daripada jumlah keseluruhan program prasiswazah di IPT.",
         numerator_label="Bilangan Program Melaksana OGC", denominator_label="Jumlah Program",
         unit="percent", aggregation="pooled_ratio", subset_ratio=True,
         data_owner="BPPT, JPT | BIPD, JPPKK | Bahagian Akademik, Pusat Antarabangsa, Unit e-pembelajaran",
         targets=_t(2, 4, 6, 8, 10), source_ref="Slaid 12, 13, 14",
         confirmation_notes=["Formula menggunakan 'Jumlah Program' manakala sasaran menyebut 'program prasiswazah' — sahkan skop penyebut.",
                             "Keberhasilan menyebut penyertaan pelajar tetapi pengukuran berasaskan bilangan program."]),
    dict(id=4, code="T1/OS3/A", teras=1, title="Kursus Pemikiran Reka Bentuk",
         indicator="Graduan mengikuti kursus pemikiran reka bentuk (design thinking)",
         definition="Melatih pelajar menyelesaikan masalah kompleks melalui pendekatan design thinking secara iteratif berteraskan kes industri sebenar.",
         outcome_2030="Peningkatan graduan dengan keupayaan penyelesaian masalah kompleks. 10% bilangan graduan yang mengikuti kursus design thinking sepanjang pengajian.",
         numerator_label="Bilangan Graduan Mengikuti Kursus", denominator_label="Jumlah Graduan",
         unit="percent", aggregation="pooled_ratio", subset_ratio=True,
         data_owner="BKA, JPT | BK, JPPKK | Bahagian Akademik, Fakulti, Pusat Inovasi",
         targets=_t(2, 4, 6, 8, 10), source_ref="Slaid 12, 13, 14", confirmation_notes=[]),
    dict(id=5, code="T1/OS3/B", teras=1, title="Pembelajaran Bersama Komuniti (SULAM)",
         indicator="Program SULAM dengan penarafan lima bintang",
         definition="Program Service Learning Malaysia-University for Society (SULAM) yang lebih berstruktur, jangka panjang dan berimpak.",
         outcome_2030="Pembentukan graduan dengan minda ke hadapan melalui program SULAM jangka panjang dan lestari. 10% program SULAM dengan penarafan lima bintang.",
         numerator_label="Bilangan Program SULAM 5 Bintang", denominator_label="Jumlah Program SULAM",
         unit="percent", aggregation="pooled_ratio", subset_ratio=True,
         data_owner="BKA, JPT | BK, JPPKK | Bahagian Akademik, HEP, Pusat Komuniti, Fakulti",
         targets=_t(2, 4, 6, 8, 10), source_ref="Slaid 12, 13, 14",
         confirmation_notes=["Instrumen dan badan penarafan lima bintang SULAM perlu dinyatakan."]),
    dict(id=6, code="T2/OS1/A", teras=2, title="Penawaran Kursus Industri",
         indicator="Penawaran kursus industri bagi program pengajian dengan kadar GBSK <70.1%",
         definition="Mengintegrasikan pengalaman industri ke dalam pengajaran dan pembelajaran melalui kursus yang ditawarkan oleh industri.",
         outcome_2030="100% program pengajian diploma dan ijazah pertama yang merekodkan GBSK di bawah 70.1% perlu mempunyai sekurang-kurangnya 1 kursus ditawarkan oleh industri.",
         numerator_label="Bilangan Program Pengajian Mempunyai 1 Kursus Industri", denominator_label="Jumlah Program Pengajian",
         unit="percent", aggregation="pooled_ratio", subset_ratio=True,
         data_owner="BKA, JPT | BKIK, JPPKK | Bahagian Akademik, Fakulti",
         targets=_t(20, 40, 60, 80, 100), source_ref="Slaid 16, 17, 18, 33",
         attestations=["Pembilang dan penyebut hanya merangkumi program pengajian diploma dan ijazah pertama yang merekodkan GBSK di bawah 70.1% (kelayakan sasaran slaid 18)."],
         confirmation_notes=["Formula slaid 18 menyebut 'Jumlah Program Pengajian' tanpa kelayakan; sasaran mengehadkan kepada program diploma/ijazah pertama dengan GBSK <70.1%. Sistem mewajibkan pengesahan kelayakan oleh IPT — perlu diperakukan KPT.",
                             "Tahun rujukan GBSK (Kajian Pengesanan Graduan tahun mana) perlu ditetapkan."]),
    dict(id=7, code="T2/OS1/B", teras=2, title="Latihan Industri Terancang",
         indicator="Penawaran pekerjaan oleh organisasi latihan industri",
         definition="Menempatkan pelajar di organisasi yang disahkan institusi supaya latihan selaras dengan bidang pengajian dan memberi pengalaman kerja sebenar yang relevan.",
         outcome_2030="Peningkatan berterusan kadar pengambilan graduan ke dalam pekerjaan selepas latihan. 40% graduan ditawarkan pekerjaan oleh organisasi latihan industri.",
         numerator_label="Bilangan Graduan Ditawarkan Pekerjaan Oleh Organisasi Tempat LI", denominator_label="Jumlah Graduan Menjalani LI",
         unit="percent", aggregation="pooled_ratio", subset_ratio=True,
         data_owner="BKA, JPT | BHI, JPT | BIPD, JPPKK | BKIK, JPPKK | Unit Latihan Industri, Fakulti",
         targets=_t(32, 34, 36, 38, 40), source_ref="Slaid 16, 17, 18", confirmation_notes=[]),
    dict(id=8, code="T2/OS2/A", teras=2, title="Pensijilan Industri/Profesional",
         indicator="Pengintegrasian pensijilan profesional/industri dalam kurikulum sedia ada",
         definition="Mengintegrasikan kandungan pensijilan industri/profesional ke dalam kurikulum sedia ada.",
         outcome_2030="10% program pengajian ijazah pertama mengintegrasikan pensijilan industri/profesional dalam kurikulum sedia ada.",
         numerator_label="Bilangan Program Pengajian Ijazah Pertama Mengintegrasikan Pensijilan Industri/ Profesional", denominator_label="Jumlah Pengajian Ijazah Pertama",
         unit="percent", aggregation="pooled_ratio", subset_ratio=True,
         data_owner="BKA, JPT | BJI, JPT | BKIK, JPPKK | Bahagian Akademik, Fakulti | Badan Profesional, Industri",
         targets=_t(2, 4, 6, 8, 10), source_ref="Slaid 16, 17, 18",
         confirmation_notes=["Penyebut tertulis 'Jumlah Pengajian Ijazah Pertama' — ditafsir sebagai jumlah program ijazah pertama; perlu disahkan.",
                             "Kebolehgunaan kepada Politeknik/Kolej Komuniti yang kebanyakannya menawarkan diploma/sijil."]),
    dict(id=9, code="T2/OS2/B", teras=2, title="Kemahiran Boleh Pindah",
         indicator="Penguasaan kemahiran boleh pindah",
         definition="Mengiktiraf kemahiran boleh pindah termasuk kemahiran digital, AI dan kemahiran baharu melalui kursus akademik, kursus TVET, pensijilan kompetensi dan pengalaman kerja.",
         outcome_2030="18% graduan memiliki sekurang-kurangnya satu kemahiran boleh pindah yang diiktiraf melalui pensijilan micro-credential/industri/profesional sebelum tamat pengajian.",
         numerator_label="Bilangan Graduan Memiliki Satu Kemahiran Boleh Pindah Diiktiraf", denominator_label="Jumlah Graduan",
         unit="percent", aggregation="pooled_ratio", subset_ratio=True,
         data_owner="BKA, JPT | BHI, JPT | BK, JPPKK | BKIK, JPPKK | Bahagian Akademik, Pusat Kemahiran, Fakulti",
         targets=_t(10, 12, 14, 16, 18), source_ref="Slaid 16, 17, 18",
         confirmation_notes=["Senarai pensijilan yang 'diiktiraf' perlu ditetapkan."]),
    dict(id=10, code="T3/OS1/A", teras=3, title="Hab Reka Cipta — Harta Intelek",
         indicator="Produk inovasi pelajar didaftarkan harta intelek setiap tahun (Made by Malaysia IPT)",
         definition="Hab pembangunan inovasi pelajar untuk menyelesaikan isu komuniti dan negara: penjanaan idea, pembangunan dan pengujian prototaip, bimbingan teknikal serta sokongan kemudahan.",
         outcome_2030="Peningkatan pendaftaran harta intelek bagi produk inovasi pelajar (Made by Malaysia IPT). 25 produk inovasi (kumulatif) yang diketuai oleh pelajar didaftarkan harta intelek.",
         numerator_label="Bilangan pendaftaran harta intelek bagi produk inovasi pelajar (Made by Malaysia IPT) setiap tahun", denominator_label=None,
         unit="count", aggregation="sum_distinct_items", subset_ratio=False, itemised=True,
         data_owner="BPS, KPT | BKPI, JPT | BHEP, JPT | PPI, JPPKK | BAPP, JPPKK | Pusat Inovasi IPT, Fakulti, Pusat Keusahawanan",
         targets=_t(5, 5, 5, 5, 5), source_ref="Slaid 20, 21, 22, 33",
         cumulative_target=25,
         items_schema=[{"key": "ref", "label": "No. rujukan pemfailan/pendaftaran HI", "required": True},
                       {"key": "title", "label": "Nama produk inovasi", "required": True},
                       {"key": "ip_type", "label": "Jenis HI (paten/reka bentuk/hak cipta/cap dagangan)", "required": True},
                       {"key": "date", "label": "Tarikh pendaftaran", "required": False}],
         attestations=["Setiap produk diketuai oleh pelajar dan didaftarkan harta intelek dalam tahun pelaporan."],
         confirmation_notes=["Sasaran tahunan 5 dan kumulatif 25 — sahkan sama ada sasaran ini peringkat nasional (dianggap nasional dalam sistem) atau setiap IPT.",
                             "Takrif 'didaftarkan' (pemfailan vs pemberian) dan peraturan produk milik bersama beberapa IPT. Sistem mengecualikan rujukan HI pendua dalam agregat nasional."]),
    dict(id=11, code="T3/OS1/B", teras=3, title="Pencapaian Inovasi Pelajar",
         indicator="Pelajar terlibat dalam program bakat inovator/pertandingan inovasi global",
         definition="Mekanisme pengumpulan dan pemprofilan pencapaian inovasi pelajar secara berstruktur melalui Pusat Inovasi Pelajar di bawah seliaan Pusat Inovasi IPT.",
         outcome_2030="Peningkatan penyertaan dan pembangunan bakat inovator serta pertandingan inovasi di peringkat global. 1% penyertaan dan pembangunan bakat inovator global.",
         numerator_label="Bilangan Pelajar Terlibat Dalam Program Bakat Inovator/ Pertandingan Inovasi Global", denominator_label="Jumlah Enrolmen",
         unit="percent", aggregation="pooled_ratio", subset_ratio=True,
         data_owner="BKPI, JPT | BHEP, JPT | BAPP, JPPKK | Pusat Inovasi IPT, Fakulti, Pusat Keusahawanan",
         targets=_t(0.2, 0.4, 0.6, 0.8, 1), source_ref="Slaid 20, 21, 22",
         confirmation_notes=["Senarai program/pertandingan yang layak dikira sebagai 'global'."]),
    dict(id=12, code="T3/OS2/A", teras=3, title="High-value Gig and Job Creator",
         indicator="Graduan usahawan yang mewujudkan peluang pekerjaan baharu",
         definition="Laluan berstruktur untuk pelajar menjana pendapatan melalui ekonomi gig bernilai tinggi yang selari dengan bidang pengajian serta menyokong pengambilan rakan sekerja atau pembentukan pasukan kecil.",
         outcome_2030="6% graduan usahawan yang mewujudkan peluang pekerjaan baharu (Pencipta Pekerjaan atau Usahawan Majikan).",
         numerator_label="Bilangan Graduan Usahawan yang Memiliki Perniagaan/ Perusahaan dan Menggaji Sekurang-kurangnya Seorang Pekerja Selain Dirinya", denominator_label="Jumlah Enrolmen",
         unit="percent", aggregation="pooled_ratio", subset_ratio=False,
         data_owner="BPS, JPT | BHEP, JPT | BAPP, JPPKK | Pusat Inovasi IPT | Pusat Keusahawanan | Fakulti/Pusat Pengajian",
         targets=_t(2, 3, 4, 5, 6), source_ref="Slaid 20, 21, 22",
         confirmation_notes=["Pembilang ialah GRADUAN tetapi penyebut ialah JUMLAH ENROLMEN (populasi berbeza). Sistem mengikut formula slaid 22 tanpa ubahsuai — perlu disahkan.",
                             "Sasaran keberhasilan menyebut '6% graduan usahawan', yang mungkin bermaksud penyebut 'graduan usahawan'."]),
    dict(id=13, code="T3/OS2/B", teras=3, title="Mentor Usahawan Alumni",
         indicator="Usahawan pelajar menjalani program imersif di syarikat alumni",
         definition="Program imersif berstruktur bersama alumni usahawan bagi pendedahan langsung kepada operasi perniagaan dan pengurusan syarikat pemula.",
         outcome_2030="1% Peningkatan usahawan pelajar menjalankan program imersif di syarikat usahawan alumni.",
         numerator_label="Bilangan Usahawan Pelajar Menjalani Program Imersif di Syarikat Alumni", denominator_label="Jumlah Enrolmen",
         unit="percent", aggregation="pooled_ratio", subset_ratio=True,
         data_owner="BHEP, JPT | BAPP, JPPKK | Pusat Inovasi IPT | Pusat Keusahawanan | Pusat Jaringan Alumni | Fakulti/Pusat Pengajian",
         targets=_t(0.2, 0.4, 0.6, 0.8, 1), source_ref="Slaid 20, 21, 22",
         confirmation_notes=["Sasaran ditulis '1% Peningkatan' — sahkan sama ada 1% ialah tahap (kadar) atau peningkatan mata peratusan."]),
    dict(id=14, code="T4/OS1/A", teras=4, title="Alumni Career Networking",
         indicator="Graduan mendapat tawaran pekerjaan oleh alumni",
         definition="Memperkukuh jaringan kerjaya antara akademia, alumni dan industri — alumni membimbing pelajar, membuka akses latihan industri dan peluang pekerjaan.",
         outcome_2030="Peningkatan peluang latihan industri/tawaran kerja oleh alumni. 5% graduan yang mendapat tawaran pekerjaan oleh alumni.",
         numerator_label="Bilangan Graduan Mendapat Tawaran Pekerjaan Oleh Alumni", denominator_label="Jumlah Enrolmen",
         unit="percent", aggregation="pooled_ratio", subset_ratio=False,
         data_owner="BHI, JPT | BAPP, JPPKK | Pusat Alumni | Pusat Kerjaya",
         targets=_t(1, 2, 3, 4, 5), source_ref="Slaid 24, 25, 26",
         confirmation_notes=["Pembilang ialah GRADUAN tetapi penyebut ialah JUMLAH ENROLMEN; sasaran menyebut '5% graduan'. Sistem mengikut formula slaid 26 — perlu disahkan."]),
    dict(id=15, code="T4/OS1/B", teras=4, title="Projek Industri",
         indicator="Pelajar terlibat dalam projek industri",
         definition="Pembelajaran berasaskan projek yang melibatkan pelajar, pensyarah dan industri untuk menyelesaikan cabaran sebenar organisasi.",
         outcome_2030="50% pelajar terlibat dalam projek pembelajaran berasaskan industri.",
         numerator_label="Bilangan Pelajar Terlibat Dalam Projek Berasaskan Industri", denominator_label="Jumlah Enrolmen",
         unit="percent", aggregation="pooled_ratio", subset_ratio=True,
         data_owner="BHI, JPT | BIPD, JPPKK | Fakulti/Pusat Pengajian | Bahagian Akademik",
         targets=_t(10, 20, 30, 40, 50), source_ref="Slaid 24, 25, 26", confirmation_notes=[]),
    dict(id=16, code="T4/OS2/A", teras=4, title="Industry on Campus / Campus on Industry",
         indicator="Pelajar memperoleh sijil latihan kepakaran daripada IoC/CoI",
         definition="Hubungan dua hala kampus–industri: makmal bersama, syarikat simulasi, makmal produksi, hab inovasi, penyeliaan bersama atau sesi pembelajaran di fasiliti industri.",
         outcome_2030="60 pelajar yang memperoleh sijil latihan kepakaran daripada program IoC/CoI.",
         numerator_label="Bilangan pelajar memperoleh sijil latihan kepakaran daripada IoC/CoI", denominator_label=None,
         unit="count", aggregation="sum", subset_ratio=False,
         data_owner="BHI, JPT | BKIK, JPPKK | Fakulti/Pusat Pengajian | Pusat Kerjaya",
         targets=_t(20, 30, 40, 50, 60), source_ref="Slaid 24, 25, 26, 33",
         confirmation_notes=["Sasaran 20–60 pelajar — sahkan sama ada sasaran nasional (dianggap nasional dalam sistem) atau setiap IPT.",
                             "Peraturan pelajar yang memperoleh lebih daripada satu sijil (kiraan unik vs kiraan sijil)."]),
    dict(id=17, code="T4/OS2/B", teras=4, title="Indeks Kepuasan Majikan",
         indicator="Peratus IPTA mencapai skor cemerlang dalam Indeks Kepuasan Majikan",
         definition="Mekanisme nasional untuk menilai kualiti pelajar dan graduan berdasarkan perspektif majikan bagi penambahbaikan kurikulum, latihan industri dan pembangunan pelajar.",
         outcome_2030="Peningkatan Indeks Kepuasan Majikan terhadap graduan IPTA. 75% pencapaian Indeks Kepuasan Majikan dengan skor cemerlang oleh setiap IPTA (slaid 33: pencapaian skor 4-5).",
         numerator_label="Bilangan IPTA mencapai skor cemerlang (skor 4–5) dalam Indeks Kepuasan Majikan",
         denominator_label="Jumlah IPTA yang dinilai dalam Indeks Kepuasan Majikan",
         unit="index", aggregation="share_of_institutions", subset_ratio=True,
         data_owner="BHI, JPT | BKIK, JPPKK | Pusat Kerjaya | Pusat Latihan Industri",
         targets=[{"value": 50, "kind": "milestone", "label": "50% — Pembangunan Indeks"},
                  {"value": 100, "kind": "milestone", "label": "100% — Selesai Pembangunan Indeks"},
                  {"value": 60, "kind": "value", "label": None},
                  {"value": 70, "kind": "value", "label": None},
                  {"value": 75, "kind": "value", "label": None}],
         source_ref="Slaid 24, 25, 26, 33",
         applicable_categories=["UA"],
         index_scale=[1, 5], excellence_threshold=4,
         confirmation_notes=["2026–2027 ialah milestone pembangunan indeks (50% dan 100% 'Selesai Pembangunan Indeks'), BUKAN skor kepuasan. Sistem merekodnya sebagai kemajuan pembangunan peringkat nasional oleh KPT.",
                             "Skala skor indeks (diandaikan 1–5) dan ambang 'cemerlang' (slaid 33: skor 4–5) perlu diperakukan.",
                             "Skop 'IPTA' — sistem menghadkan kepada kategori Universiti Awam; sahkan sama ada Politeknik/Kolej Komuniti/IPTS terlibat."]),
    dict(id=18, code="T5/OS1/A", teras=5, title="Program Quintuple Helix",
         indicator="Program Quintuple Helix dilaksanakan oleh kolej kediaman",
         definition="Budaya kepimpinan pelajar berintegriti yang menghubungkan IPT, industri, kerajaan, komuniti dan alam sekitar dalam program berimpak.",
         outcome_2030="10 program Quintuple Helix dilaksanakan oleh Kolej Kediaman.",
         numerator_label="Bilangan program Quintuple Helix yang dilaksanakan oleh Kolej Kediaman", denominator_label=None,
         unit="count", aggregation="sum_distinct_items", subset_ratio=False, itemised=True,
         data_owner="BHEP, JPT | BAPP, JPPKK | MAPENA | HEP | Kolej Kediaman | Fakulti | Bahagian Jaringan Industri",
         targets=_t(2, 4, 6, 8, 10), source_ref="Slaid 28, 29, 30",
         items_schema=[{"key": "ref", "label": "Kod/rujukan program", "required": True},
                       {"key": "title", "label": "Nama program", "required": True},
                       {"key": "college", "label": "Kolej kediaman pelaksana", "required": True},
                       {"key": "date", "label": "Tarikh pelaksanaan", "required": False}],
         confirmation_notes=["Sasaran 2–10 program — sahkan sama ada nasional atau setiap IPT, dan sama ada tahunan atau kumulatif.",
                             "Kriteria program 'Quintuple Helix' (lima heliks yang wajib terlibat)."]),
    dict(id=19, code="T5/OS1/B", teras=5, title="Kursus Literasi ESG",
         indicator="Pelajar mengikuti Kursus Literasi ESG",
         definition="Meningkatkan kefahaman pelajar tentang kelestarian, tanggungjawab sosial dan tadbir urus beretika.",
         outcome_2030="60% pelajar mengikuti Kursus Literasi ESG.",
         numerator_label="Bilangan pelajar mengikuti Kursus Literasi ESG", denominator_label="Jumlah Enrolmen",
         unit="percent", aggregation="pooled_ratio", subset_ratio=True,
         data_owner="BKA, JPT | BHEP, JPT | BK, JPPKK | MAPENA | HEP | Bahagian Akademik | Fakulti | Kolej Kediaman",
         targets=_t(5, 15, 30, 45, 60), source_ref="Slaid 28, 29, 30",
         confirmation_notes=["Sama ada pelajar dikira kumulatif (pernah mengikuti) atau dalam tahun pelaporan sahaja."]),
    dict(id=20, code="T5/OS1/C", teras=5, title="Peneraju Kesihatan Bumi",
         indicator="Pelajar terlibat dalam aktiviti kesihatan bumi",
         definition="Memperkasa pelajar menerajui aktiviti kelestarian dan perubahan iklim: aktiviti lapangan, pemuliharaan alam sekitar, pengurangan jejak karbon, kesihatan komuniti dan projek perubahan iklim.",
         outcome_2030="700 pelajar yang terlibat dalam aktiviti berasaskan kesihatan bumi.",
         numerator_label="Bilangan pelajar terlibat dalam aktiviti kesihatan bumi", denominator_label=None,
         unit="count", aggregation="sum", subset_ratio=False,
         data_owner="BHEP, JPT | BAPP, JPPKK | MAPENA | HEP | Fakulti | Kolej Kediaman | Rakan Komuniti/Industri",
         targets=_t(300, 400, 500, 600, 700), source_ref="Slaid 28, 29, 30",
         confirmation_notes=["Sasaran 300–700 pelajar — sahkan sama ada nasional atau setiap IPT.",
                             "Pelajar yang menyertai beberapa aktiviti: kiraan unik diandaikan."]),
]
# fmt: on

for _k in KPI_CATALOGUE:
    _k["os_code"] = _k["code"].rsplit("/", 1)[0]
    _k["os_name"] = OBJEKTIF[_k["os_code"]]
    _k.setdefault("attestations", [])
    _k.setdefault("itemised", False)
    _k["measurement"] = (
        f"({_k['numerator_label']} ÷ {_k['denominator_label']}) × 100%" if _k["unit"] == "percent"
        else _k["numerator_label"] if _k["unit"] == "count"
        else "Peratus IPTA mencapai skor cemerlang dalam Indeks Kepuasan Majikan"
    )

KPI_BY_CODE = {k["code"]: k for k in KPI_CATALOGUE}
KPI_BY_ID = {k["id"]: k for k in KPI_CATALOGUE}


def kpi_config(entry: dict) -> dict:
    """The JSON configuration persisted in kpis.config_json."""
    return {
        "attestations": entry.get("attestations", []),
        "items_schema": entry.get("items_schema"),
        "applicable_categories": entry.get("applicable_categories"),
        "index_scale": entry.get("index_scale"),
        "excellence_threshold": entry.get("excellence_threshold"),
        "cumulative_target": entry.get("cumulative_target"),
        "target_scope": "national",
    }

# Backwards-compatible tuple list used by Pilot V2B (id, teras, title, unit, targets)
KPIS = [(k["id"], k["teras"], k["title"], {"percent": "percent", "count": "count", "index": "percent"}[k["unit"]],
         [t["value"] if t["kind"] == "value" else None for t in k["targets"]]) for k in KPI_CATALOGUE]
