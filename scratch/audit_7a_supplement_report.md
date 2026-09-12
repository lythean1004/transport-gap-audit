# 7A' 산출물 보완 확인 결과

## [확인 1] `route_service_hours.parquet` 값 수준 점검

### intervaltime 계열 컬럼
- `intervaltime`: non-null=12, NaN=0, min=12.0, median=15.0, max=50.0
  - 전체 값(12행): [13.0, 12.0, 25.0, 12.0, 15.0, 20.0, 15.0, 15.0, 30.0, 12.0, 50.0, 25.0]
- `intervalsattime`: non-null=12, NaN=0, min=30.0, median=42.5, max=120.0
  - 전체 값(12행): [30.0, 30.0, 70.0, 30.0, 40.0, 60.0, 40.0, 40.0, 50.0, 60.0, 120.0, 45.0]
- `intervalsuntime`: non-null=12, NaN=0, min=30.0, median=42.5, max=120.0
  - 전체 값(12행): [30.0, 30.0, 70.0, 30.0, 40.0, 60.0, 40.0, 40.0, 50.0, 60.0, 120.0, 45.0]

### first_bus_ok / last_bus_ok
- `first_bus_ok`: {np.True_: 12}
- `last_bus_ok`: {np.True_: 12}

**결론**: `first_bus_ok`, `last_bus_ok`에 값이 채워진 행이 있습니다.

### citycode
- parquet 고유값과 건수: {'31130': 12}
- **방향별 분리 여부**: 모든 routeid가 1건씩만 존재하므로 방향별로 분리되어 있지 않음.

## [확인 2] 미커버 3개 노선의 실제 비중

### citycode 대조
- arrival_raw 고유 citycode: set()
  - parquet의 citycode 집합과 불일치함.

### arrival_raw routeid별 관측 레코드 수
| routeid | 레코드 수 | 비중 |
|---|---|---|
| GGB222000009 | 376 | 8.0% |
| GGB222000013 | 376 | 8.0% |
| GGB222000027 | 376 | 8.0% |
| GGB222000028 | 376 | 8.0% |
| GGB222000031 | 376 | 8.0% |
| GGB222000032 | 376 | 8.0% |
| GGB222000048 | 376 | 8.0% |
| GGB222000199 | 376 | 8.0% |
| GGB234000028 | 376 | 8.0% |
| GGB222000180 | 375 | 8.0% |
| GGB234000003 | 374 | 7.9% |
| GGB222000078 | 370 | 7.9% |
| GGB222000137 | 144 | 3.1% |
| GGB222000239 | 34 | 0.7% |
| GGB222000056 | 28 | 0.6% |
| **합계** | **4709** | **100.0%** |

### 3개 노선 비중
- GGB222000056: 28건 (0.6%)
- GGB222000137: 144건 (3.1%)
- GGB222000239: 34건 (0.7%)
- **3개 합산**: 206건 (4.4%)

- 노선 수 기준 커버리지: 12/15 (80.0%)
- 관측 가중 커버리지: 4503/4709 (95.6%)

## [확인 3] 3개 노선 누락 원인
- 7A' 입력이 될 만한 `src/` 및 `config/` 하위 파일에서 해당 3개 노선을 찾지 못함.
- evidence/route_info/ 내 비정상 파일(비-00, 파싱오류) 없음.

**원인 판정**: 
호출 미시도 (입력 대상 목록에 없었던 것으로 추정, 실패 기록 없음)

## [확인 4] 7E' 입력 경로 결정 근거

### data/staged/ 파일 목록
- .gitkeep (크기=17 bytes)
- bldg_title.parquet (크기=53086 bytes, 행수=4067)
- evidence_archive_summary.json (크기=315 bytes)
- evidence_file_manifest.csv (크기=108142 bytes)
- evidence_hash_map.csv (크기=100406 bytes)
- kapt_basic.parquet (크기=925686 bytes, 행수=21690)
- pdf_curated_events.csv (크기=133206 bytes)
- pdf_curation_summary.json (크기=341 bytes)
- pdf_document_disposition.csv (크기=25746 bytes)
- pdf_event_candidates.csv (크기=310627 bytes)
- pdf_extraction_summary.json (크기=849 bytes)
- pdf_inventory.csv (크기=96071 bytes)
- pdf_match_audit.csv (크기=15334 bytes)
- pdf_registry_matches.csv (크기=20461 bytes)
- route_service_hours.parquet (크기=10987 bytes, 행수=12)
- SRC-E1-A04_html.txt (크기=19614 bytes)
- SRC-E1-A08_html.txt (크기=7718 bytes)
- SRC-E1-A10_html.txt (크기=8733 bytes)
- SRC-E1-B02_html.txt (크기=4079 bytes)
- SRC-E1-B05_html.txt (크기=4888 bytes)
- SRC-E1-B08_html.txt (크기=20066 bytes)
- SRC-E1-B10_html.txt (크기=10233 bytes)
- SRC-E1-C08_html.txt (크기=30623 bytes)
- SRC-E2-C08_html.txt (크기=8968 bytes)
- SRC-E2-C09_html.txt (크기=20717 bytes)
- SRC-E2-C10_html.txt (크기=19731 bytes)
- staged_candidates_registry.csv (크기=97643 bytes)
- tago_citycodes.parquet (크기=1676 bytes, 행수=138)
- tago_stops_full.parquet (크기=160239 bytes, 행수=8420)
- tago_stops_nearby.parquet (크기=310247 bytes, 행수=20254)
- 1453c59d79bae2b543831e37cb145e8c1bebfe7c99937945ca331b2e3f50ce85.txt (크기=8966 bytes)
- 1929aa409048a60bb18bcd573aa1d833e8f5288a2dc71c67de384878e9c0e983.txt (크기=10212 bytes)
- 3ef0b1d078a34b107baf405f28563522fb2d7201e892d90b2c50cc7022c161a3.txt (크기=4886 bytes)
- 5e3dc3c792a689bea7d91c33a80d9f5e07cc4d43b0de3f8b1dc8fa73f4038570.txt (크기=19612 bytes)
- 6c3d1a93c9d63476d41debe4df0b96bb59f4159de5198db0d9acc604339b8c97.txt (크기=19729 bytes)
- 74cef30b17bd093346b8467ab7653e9d4bf48c1c71e30d2e0463b87a751f2a7e.txt (크기=19729 bytes)
- 8f2abee59238b852c4f3323917f18942739a69da8af7824a158d15be0d6d827e.txt (크기=4886 bytes)
- 94f68439fea6916db0a19650a07a434d4d40eb17afdb22d8a8b538d290438bd5.txt (크기=10200 bytes)
- ae8194b82cddc0fde21d8e138f5baadec3c5daee911a8cb07cbfcdb2ebf106fb.txt (크기=8966 bytes)
- c1d499491cb9e89f2a4d0fb57242a1debf0565aedc77c14fd95d8347c65cb1bc.txt (크기=8966 bytes)
- c2e29fee94e448604d13855a081c78c656b928fdbbe136cd49afd1e5323870e6.txt (크기=19729 bytes)
- c521312de632ca3c23f97f9c9d70fbf59a7154947a6b3f863e4d08b250f5cf71.txt (크기=30622 bytes)
- dd1eea25a083869bc0080717335818364f5c6e839c8171398874506adedc1b68.txt (크기=19612 bytes)
- ddc7e45e88ea1876cff45240c7ce2666654d281ec7764b0dccb7ead74b6c9e1e.txt (크기=10231 bytes)
- e32fe204aa721434cbce9866f87f1abebdb0b8a4b6f6ed5981c0e92cdd3244e6.txt (크기=4886 bytes)
- ec0d2d5fcc2938dfb44b47bb0d4321b38840780a92df423e24b8d7095d7d7b91.txt (크기=30622 bytes)
- ef6893ac2a18d7466d6b495a952303b510447bbd52fc6677d408672977ad0a3e.txt (크기=30621 bytes)
- f7c03d0606340132d776c290f10c37daa3f55471d58e18f2725e415bf8c59799.txt (크기=19612 bytes)
- PDF-065-p1.png (크기=581511 bytes)
- 083f8f6b7c56a257a98f0d1266285c1d0f002be24c227c16f382d5bcdd3f1386.txt (크기=1295 bytes)
- 08438e6ac19967e88de5ae5dfe94e8f5bd891efefd0eb07195d96045b0707fa6.txt (크기=521847 bytes)
- 0a6095cb415fbeedd0727303ba11c005733bf4f2d7721122b6d577220077c258.txt (크기=4427 bytes)
- 0f2f8e767b8aaf98df7013e0bdfb1f133a23c7e784c22ac5ab774d071ffa4e37.txt (크기=380279 bytes)
- 0fe071799169540ddae02383e3dcd67457b752ddf6d52e1f0881c4811e3aa8c1.txt (크기=567201 bytes)
- 14d43f72c1bb4607b6cff9727d014a71548ad15d99861b90d0da6b55c76c35d8.txt (크기=42248 bytes)
- 17e730dc3c2b81cfa2c2e820f79ca45e50b657236b8cb5870235dfbf463083b2.txt (크기=341419 bytes)
- 17f890d3468fb4f720c33fa6aefb56dd0eb6cfae7df0b4bd9996a5b6f554de4d.txt (크기=522005 bytes)
- 1bb829548e89c9bc87d68f9d08d8950cbcd1c4a2598056dd77d8bd5a723bab5e.txt (크기=7028 bytes)
- 1c78338e3624cbdc6b2e58a875448c9fb1f5e6cecb6fba1b8bb7317940bd0094.txt (크기=7952 bytes)
- 1dac689d7133335f0bd75cc2a88000f862410209efa5bcfc9ea429ca4dc19515.txt (크기=360524 bytes)
- 1fb52b9e26ce23b6131d05e4dcf6b2e8c294a5b4aafe585c9b8b4313d706d3f6.txt (크기=351856 bytes)
- 21afbf75fd6243f1e1b87d13d67fdab22fb686efa11024477c8f375e79286055.txt (크기=50703 bytes)
- 25311d447e7f43c48655b96613b1ff2bc56371612a268932071bfb8429e5107d.txt (크기=424289 bytes)
- 2759529f5e28ddedc459b8499ccd88c52df2a3be5388dd8afaab954540cad938.txt (크기=106974 bytes)
- 2a3f750b161fd40b3fe721027885cc698b4e8456e20cc2ded266c64a03eb85ca.txt (크기=11326 bytes)
- 35c0ffd16b7581c3888e2559c2e9d9d71dc598c9243d1ff23162619533ae7729.txt (크기=5567 bytes)
- 35fef79a31d18fdeecb52bc6a15e08811e6857245dbd14d220753f3597a10981.txt (크기=391551 bytes)
- 4c96f574d6f235f71d79e3e067d5d2f666e5895a0c0db9ae0b862e31aa96c14d.txt (크기=195073 bytes)
- 50d654cd580f52ccc58acbffa76dfcea48478ad52a0346f7885b037e5804215e.txt (크기=2567 bytes)
- 543077ecbacfb56aba75f592cde54280c508f1c5653cf9a25b3196a9c060df3d.txt (크기=2456 bytes)
- 548a8ff7ef6d0fd6ce3db6989f1392e926873d063fe4344760061cb9d3637fea.txt (크기=4624 bytes)
- 565721aa8e656d20e2b2edb9c8db64b0ffdab8bfd02ea4e2ad8119bc9b76e5d9.txt (크기=424341 bytes)
- 5c8bd8f5fb2ae4023300d399bf8deb93f05dd5dff08af27165cd6c6a2201d89c.txt (크기=4420 bytes)
- 5ca5a14c242fdc43aba2946d19a90fd682ecf38054edf2acaaa843cc89f8112b.txt (크기=1296 bytes)
- 5ec7ad2f8fde7650b4723adcec0d6931c2ecdb8af0bd0ccaab60f6db6b6c63e6.txt (크기=5833 bytes)
- 5f2a920d6c4eef88fda95d7fd9fb6692d4f8aed29368d2e5a968886069317666.txt (크기=50449 bytes)
- 5f78b95ae640847279af2e71ce967b3b8f2160776ac08cf24f46e5d731c0aca5.ocr.txt (크기=65819 bytes)
- 5f78b95ae640847279af2e71ce967b3b8f2160776ac08cf24f46e5d731c0aca5.txt (크기=68 bytes)
- 5fae342e3aebe93b2118cd32e37d603c71670b7b78aad88b4b859e882a73ee3c.txt (크기=60336 bytes)
- 64d6f55fad58be64ef283ac365cab3c13752d7b05688569522b570c1f4438157.txt (크기=5454 bytes)
- 662cae34a3c8e14374c392303378b0ba439c99f3c2adc01123332b85f12a931f.txt (크기=363933 bytes)
- 672466fe557eca52389b61cf8eb9697e0f4110033cbb0418bbe8d3193d9dc68c.txt (크기=267 bytes)
- 6725ccec06129673dcd030a56859bb9c08dc0d33fa297914ba75e9197c95f38b.txt (크기=5481 bytes)
- 6a368721bcef1b229bfe5bd3bb2d40b5ddf61811dd86483a53841c6ecdfc15a4.txt (크기=5364 bytes)
- 6cdd357410777803b9423465738698e06c86d90f2770b19fe8e598acca238bb1.txt (크기=195097 bytes)
- 70517aa73243cce5a00fb02792ec0a84e4aad3c728a1a5c48546bfa0f8409442.txt (크기=309313 bytes)
- 70e61cf108214fb5b0a5bb9c687aa196fbffbb203a42f2b527b9f9a14f88e4a7.txt (크기=4360 bytes)
- 7139dab4d1a5071c526396881c1e3160f3ab1957c9f42437a0cf9a3c533885ab.txt (크기=50703 bytes)
- 720b75ef0bff8893c739dde9a900298f9a9b9f95ec74db696ec8841b828d5850.txt (크기=16769 bytes)
- 7566afe81be70a79ee692a52f0438da0bfc935eb971e853654613533d09d55c7.txt (크기=353411 bytes)
- 75b73130d02612d7c1c05f64b5a800a662554d854abc4445e565e0caf2439cb6.txt (크기=7432 bytes)
- 7714332a5b225299facb069431a9cd3ca9d7535e10986b2ec3dc5b3a7fc359a5.txt (크기=6379 bytes)
- 78e1f182e7fd0b7a08ca5d3c27ae6e6d7fda39a6479c6788bce1f18d7d80e999.txt (크기=286406 bytes)
- 7e77caac8ab8aadaad63f26fe2d9c7bb2754b437be598bcb82795b95a75c5d21.txt (크기=4008 bytes)
- 7ffd1f81084ea1df1f970a4b81c950d8c381769be3c0f1ef2ab578354b184249.txt (크기=3368 bytes)
- 808adcd9cfba65450c62f6187416790bf6dcca2d2c50af97e8ecee5c8f9a84fc.txt (크기=3412 bytes)
- 83da19e7f5e189f542899a4ff549fbf2cd6caff6dab96ef41ff11835f4e66734.txt (크기=8758 bytes)
- 894b933a4fc5a46612a01bb5806599544d52a78c702fdf34203d30d7240bac5b.txt (크기=6242 bytes)
- 8ac431b91d3d060832a9e275cef5f02f8f259cf1b8a41b8716d2cd3bc3ab32d2.txt (크기=8242 bytes)
- 8c8756bf0041e944a8ce2c1e3d1d8e3aa16e34722cd7c5643a68f09fb3e5a5d9.txt (크기=721 bytes)
- 8f0fe3faf922f11b696f2037df4e39f81f0469ee14c22ff396095a3bede4965c.txt (크기=24561 bytes)
- 90f107e315964eadde4d306bc9bd50f6b4883562335c9cbb3a6a6c4b486b8c77.txt (크기=45130 bytes)
- 90fcc484062c53afba4d33beaa9b5e0e5027ca7eea745254829727621b4dea52.txt (크기=4214 bytes)
- 91764a04183cf52a403ab40f3f4eb7de4a23120b84df4d271aa7ae5fcc0d0b83.txt (크기=5588 bytes)
- 9f8e43212a22fdd573254ea59bd1cd1ba3f8d1ac7a1494b97682b50c65adc95b.txt (크기=360385 bytes)
- a27d8c520db11a7da4c8dc60168a373f40ed7f87cbee81d6da883b550f43e871.txt (크기=4389 bytes)
- a3c74951c8e5c04931fc3d631c069bf6b22718e2978eb0d577e1941c58393e7f.txt (크기=4417 bytes)
- a462e80e674ef097b025a5d6a1fd147bba70fc5ecd04a37c12c03435d394b18d.txt (크기=3894 bytes)
- a65a5c4807f9e93fe2cd6c465ccaaccae2657d5b48db24ded879e80b26468319.txt (크기=416805 bytes)
- a7dd2379b5b5c8ef62f841f11759dc858b2f3a120b4f0f27f9ff50b737a17289.txt (크기=38423 bytes)
- a9beb607d64a9ebdabe680bf68c20f0f2cfd347c8d24d9a0a3d82b30fa1094bc.txt (크기=4123 bytes)
- ade438681fd2b080ed26cbafd823416f4d95a0df7fed95a67f508db4ccb0ac7c.txt (크기=1295 bytes)
- b0c5c614416bcefdea6f27d7eb88f9a6be6c9a728f9a8bc0380f9356db04e18d.txt (크기=63069 bytes)
- b247b3e65cb7029821c352a345952c0fb73323ae3462b90b52f5b653dca1a2f5.txt (크기=519427 bytes)
- b289b7a3fb07c631744d95e58f66b47e45e0a4347c138c16684c58554010050c.txt (크기=21320 bytes)
- b742188f7e7a4d25e76a9e308fece038462ad1460e35f54b631a7ac587408d8d.txt (크기=130709 bytes)
- bc80d2e3ee3dadbec345a636c7840673b07f8bc9da12f3a14d21a33c94ed5d33.txt (크기=8346 bytes)
- bff83f4d343364fcf84955d49a59748b9f82b4116f02cfbfb70ca9e5c3ba6b9d.txt (크기=63400 bytes)
- c527d0ab39cb4e427fa62ce8c97d7f7b5074d06dcf2ac3af96ae616ddf7fdcc9.txt (크기=2739 bytes)
- c9e00558131c031e6df06cef301f3d81f8c0f0fe4f6eab31b670b0512414feab.txt (크기=20774 bytes)
- d225b71e078de3e7903d26ef108379f624797a80735d28f23efba6334c373912.txt (크기=354615 bytes)
- d3bdc37aa3e72dd26cd4065e2019ef0154a1f93b16d3f0202d05f03b5fe8c968.txt (크기=3617 bytes)
- d647c7a4cdbee67abb44b2fdf7c64c57b821e6a427702c953cf7c3758cc537e6.txt (크기=2308 bytes)
- d7e578abba3c7c6fe3592dbebdaef288ee0ace8aeb5d4a35909946668e2838f1.txt (크기=13811 bytes)
- da11fbf0ece767ab2872f6f40311e00bf7df9bceafc4f9ce045d9c29bb28ed92.txt (크기=4681 bytes)
- dbf2922f167bc6ed4a6e634ca45cd33925611b91d3696fffa35e4263bd88d3ad.txt (크기=2760 bytes)
- dbf7426f5af96c441bb07cbbd80a31ca690cde79a1dc426fac9700ba227bf998.txt (크기=5886 bytes)
- dc233154be5b674cb88e215791cc0f37d90bdbe94d06dff17e6fed269a0f7d9f.txt (크기=11791 bytes)
- dfdccd29d1cffe983af2ea5d909ff6fc9c5ea5aabe1a4167e04d8ce4029f36c4.txt (크기=2579 bytes)
- e1ebc0fea640403e26a71cfea8ebace74b5da734ea1371ad0713ba9974d0da49.txt (크기=6790 bytes)
- e5df2c787de7dcb0a2e0db08463e2f03569396fed88580c86947a2197a284875.txt (크기=12131 bytes)
- e8f57f80285b5bdd4a7c065b26e86816a49adf47b0621eb892b91b0ed574c58a.txt (크기=2308 bytes)
- e9ecf26d9d265a70fb06ab20847c338f10a9bf24ef3dbf6ed58c57c6a251b931.txt (크기=269783 bytes)
- ea078d9bb489eb228f003f5675c7825a8b6223f409e3dad8375bcf6a9e780378.txt (크기=3750 bytes)
- ec903ff08af3f81b601966e19ded4bbc7ec874605458f51aa9d213ffc322d3aa.txt (크기=11043 bytes)
- ecc470f4fb71a5b29f7499ce815fe4f6605f9de139444664a3134be6e5dcd577.txt (크기=14395 bytes)
- ee97d54c55cef1585e0d54df1a891d04e68b3dbdc1c8fcde9b4cbc7ef7087556.txt (크기=19469 bytes)
- f54821ed2da56cc09c6281ab080ed96a84252a1fad9af1fff9c07bb78913eb1f.txt (크기=13907 bytes)
- f7202e924988f383730f245784e37a1ec66f0f54d655fb3b8171c45314389195.txt (크기=367163 bytes)
- f73aeb4a71997f5df77ed1b4d5cd616609805096dc5b3333ed61b3dba5b62051.txt (크기=109362 bytes)
- f7d1029283830f3ac7dfd255ec4b2f248fd38cb22aa444baaff4f759b04d80d0.txt (크기=84767 bytes)
- fb08785a7962ad8088d930c4598ac1d095187eb34f7a52ea2b675bb0f5fc72cc.txt (크기=9233 bytes)
- fbe43488370ed17260f5eb6525fcfb25d0453d9a5c2222cb252bf9de41dd62d1.txt (크기=9233 bytes)
- fe6a75eea6be0515dd7aae147197495ec4ecbc0e96e953f867d6a3d269c7dcbd.txt (크기=4216 bytes)

### 관련 검색 결과
- `tago_arrival.parquet` 명시적 요구 기술 없음.

**입력 경로 판정**: 
확인불가 (관련 명세 미발견)

## 최종 판정
**PARTIAL-GO**
- 한 줄 근거: 필수 데이터가 정상 구조로 존재하나, 관측 레코드 가중치 4.4%를 차지하는 3개 노선의 배차정보가 수집 목록 누락(호출 미시도)으로 인해 부재함.

### 사람이 결정해야 할 항목 목록
1. 미커버 3개 노선(`GGB222000056`, `GGB222000137`, `GGB222000239`)을 7E' 관측 배차 산출 대상에서 제외할지, 아니면 7A' 추가 호출을 수행하여 채울지 결정
2. 7E' 입력으로 `tago_arrival.parquet` 스테이징 단계를 먼저 개발할지, 원장/raw 파일에서 직접 읽는 방식으로 7E'를 구현할지 결정