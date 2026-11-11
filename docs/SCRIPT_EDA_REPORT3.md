# Script trình bày — Phần 3: EDA "thời điểm vàng"

Người trình bày: BanNH · Deck: 22 slide · Thời lượng dự kiến: **khoảng 25 phút** (tổng các mốc thời gian bên dưới) + hỏi đáp. Cần rút gọn thì bỏ slide 5, 6, 18 (tiết kiệm khoảng 2,5 phút).

Cách đọc file này:
- **Lời nói** là câu nói gần như nguyên văn; có thể nói tự nhiên hơn nhưng giữ đúng số.
- **Chỉ vào** là chỗ trên biểu đồ cần chỉ khi nói, để người nghe thấy bằng chứng.
- **Chuyển** là câu nối sang slide sau.
- Số liệu lấy từ `notebooks/3_EDA.Rmd` (bản đóng băng 01/11; định nghĩa Shorts cập nhật 11/11). Không nói số nào ngoài file này.
- **Shorts** = video ≤ 3 phút, theo giới hạn của YouTube từ 15/10/2024 (trước đó 60 giây). API không cho biết video dọc hay ngang, nên đây là ước lượng theo thời lượng.

Mạch trình bày: **câu hỏi → dữ liệu có tin được không → kết quả thô → kiểm tra bất thường → kiểm soát nhiễu → kết luận**. Mỗi kết luận đều có biểu đồ làm bằng chứng.

---

## Mở đầu

### Slide 1 — Bìa · 0:45
**Lời nói:** "Phần của em trả lời câu hỏi chính của đề tài: đăng video trong giờ hành chính hay giờ nghỉ thì dễ lọt Top Trending YouTube Việt Nam hơn. Hai bạn trước đã đưa dữ liệu từ YouTube về và làm sạch. Phần này dùng bản dữ liệu đã đóng băng ngày 1/11: 40.531 video, trong đó 398 video lọt chart chính."

**Chuyển:** "Trước hết, em nói cách đọc các con số trong phần này."

### Slide 2 — Cách đọc kết quả · 1:15
**Lời nói:** "Giờ hành chính là 8 giờ sáng tới trước 5 giờ chiều, thứ 2 tới thứ 6, giờ Việt Nam. Còn lại là giờ nghỉ, gồm cả cuối tuần. Một video được tính là lọt trending nếu có mặt trên chart mostPopular Việt Nam trong 72 giờ đầu.

Mỗi kết quả là một tỉ lệ: số video lọt chart chia cho tổng số video trong nhóm, luôn kèm khoảng tin cậy 95%. Để so hai khung giờ, em dùng tỉ số giờ nghỉ chia giờ hành chính: bằng 1 là không khác biệt.

Bên phải là hai tập dữ liệu sạch: chart chính dùng 40.531 video, chart theo danh mục dùng 39.669 video, vì hai chart được chụp theo lịch khác nhau."

**Chuyển:** "Câu hỏi đầu tiên: tập sạch này có tin được không?"

---

## A–B. Dữ liệu có tin được không

### Slide 3 — Tập sạch dồn vào 14 ngày · 1:15
**Chỉ vào:** đường đỏ (is_clean) so với đường xám (cohort); các đoạn đường đỏ rơi về 0.

**Lời nói:** "Đường xám là toàn bộ video mới, đường đỏ là video còn lại sau khi lọc độ phủ crawler. Lọc giữ lại khoảng 26%. Nhưng đường đỏ chỉ có giá trị ở cuối tháng 9 và 3 ngày lẻ: 10, 12 và 19 tháng 10. Các ngày khác bằng 0, vì crawler tắt dài, có lần 94 giờ liên tục. Vậy tập sạch đại diện cho 14 ngày, không phải cả tháng."

**Chuyển:** "Việc dồn ngày này có làm lệch khung giờ không?"

### Slide 4 — Lệch theo thứ, không lệch theo khung giờ · 1:15
**Chỉ vào:** cột T2 bên trái; vùng nền vàng 08–16h bên phải.

**Lời nói:** "Bên trái: vì 12/10 và 19/10 đều là thứ 2, thứ 2 chiếm 36% tập sạch, trong khi ở dữ liệu gốc chỉ 16%. Đây là một độ lệch cần nhớ.

Bên phải là câu hỏi quan trọng hơn: bộ lọc có loại video giờ hành chính nhiều hơn không? Đường đỏ là phần trăm video qua được ngưỡng, theo giờ đăng. Trong vùng vàng, tức giờ hành chính, đường này không thấp hơn các giờ khác: 27,9% so với 25,5% của giờ nghỉ. Chỉ video đăng khuya 23 giờ tới 2 giờ là khó qua ngưỡng. Kết luận: so sánh khung giờ được, nhưng phải kiểm soát ngày đăng."

**Chuyển:** "Tiếp theo là video được đăng vào lúc nào."

### Slide 5 — Video đăng lúc nào · 0:45
**Chỉ vào:** đỉnh 17–19h và đỉnh 11h.

**Lời nói:** "Video đăng nhiều nhất lúc 17 tới 19 giờ, chiếm 26%, và lúc 11 giờ. Giờ hành chính chiếm 35%, cuối tuần 32%, tối ngày thường 24%. Mỗi nhóm đều có hàng nghìn video, đủ để so sánh."

**Chuyển:** "Hai biến kiểm soát quan trọng là thời lượng và danh mục."

### Slide 6 — Thời lượng và danh mục · 1:00
**Chỉ vào:** đỉnh nhọn ở 60 giây và vạch 180 giây trong histogram; thanh Tin tức bên phải.

**Lời nói:** "Thời lượng có đỉnh nhọn đúng ở 60 giây, giới hạn Shorts trước tháng 10/2024. Từ 15/10/2024 Shorts dài tối đa 3 phút; tính theo mốc này, Shorts chiếm 57% số video. Thời lượng và số subscriber đều lệch rất mạnh nên em dùng thang log hoặc chia nhóm. Bên phải: ba danh mục lớn nhất là Blog, Tin tức, Giải trí, chiếm 69%. Tin tức đăng rất nhiều: 10 kênh đăng nhiều nhất, chủ yếu kênh tin tức, chiếm 12% số video."

**Chuyển:** "Bây giờ vào kết quả chính: tỉ lệ lọt trending theo giờ đăng."

---

## C. Tỉ lệ trending theo thời điểm đăng

### Slide 7 — Tỉ lệ theo từng giờ · 1:15
**Chỉ vào:** các chấm vàng 9–15h nằm dưới đường gạch; chấm 17h.

**Lời nói:** "Mỗi chấm là tỉ lệ lọt chart chính theo giờ đăng, thanh dọc là khoảng tin cậy. Đường gạch là mức chung 0,98%. Các chấm vàng, tức 9 tới 15 giờ, đều nằm dưới đường gạch; thấp nhất là 13 giờ, chỉ 0,2%. Cao nhất là 17 giờ, 2,3%, gấp hơn 2 lần mức chung.

Chấm 4 giờ sáng cao bất thường, 7,1%, nhưng chỉ có 337 video và 14 trong 24 video trending đến từ 2 kênh, một kênh blog và một kênh âm nhạc, đều là livestream, nên đó là chuyện của kênh, không phải của giờ. Các giờ 0–3 giờ có thanh rất dài vì quá ít video, em không kết luận."

**Chuyển:** "Gộp lại theo khung giờ thì sao?"

### Slide 8 — Hành chính hay nghỉ · 1:30
**Chỉ vào:** hai thẻ bên phải; chấm vàng ở hàng trên cùng của ô "Chart chính".

**Lời nói:** "Giờ hành chính lọt chart chính 0,62%, giờ nghỉ 1,18%, gấp 1,9 lần. Hai khoảng tin cậy không chồng lên nhau, nên chênh lệch lớn hơn nhiều so với độ nhiễu.

Khi tách giờ nghỉ thành 3 đoạn: tối ngày thường cao nhất, 1,33%, gấp 2,1 lần giờ hành chính dù cùng là thứ 2 tới thứ 6. Cuối tuần lại thấp nhất trong giờ nghỉ. Vậy chênh lệch không phải do cuối tuần.

Ô bên phải là chart danh mục: các đoạn chênh nhau ít, khoảng tin cậy chồng nhau."

**Chuyển:** "Nhưng nhớ lại tập sạch dồn vào thứ 2. Em kiểm tra xem điều đó có làm sai kết quả không."

### Slide 9 — Tỉ lệ nền giảm 3 lần · 1:15
**Chỉ vào:** các chấm xanh (đợt 1) so với 3 chấm đỏ (đợt 2).

**Lời nói:** "Mỗi chấm là tỉ lệ trending của một ngày. Đợt 1 cuối tháng 9, các chấm quanh 1–2%, trung bình 1,32%. Đợt 2 chỉ còn 0,44%. Lý do: chart vẫn chỉ có khoảng 200 chỗ, nhưng số video mới mỗi ngày tăng từ khoảng 2.700 lên 7.300 tới 8.600 khi nhóm mở rộng danh sách kênh. Vấn đề là 2 ngày thứ 2 của đợt 2 chiếm 48%, gần một nửa video giờ hành chính, nên kéo tỉ lệ giờ hành chính xuống."

**Chuyển:** "Vậy nếu so trong cùng nhóm ngày thì chênh lệch còn không?"

### Slide 10 — So trong cùng nhóm ngày · 1:15
**Chỉ vào:** hàng T2 nhạt màu; ô chiều thứ 3–6 đậm; bảng bên phải.

**Lời nói:** "Heatmap theo thứ và buổi. Hàng thứ 2 nhạt ở sáng, chiều, tối, đó là ảnh hưởng của đợt 2; ô đêm thứ 2 cao hơn nhưng chỉ có 12 video trending. Bảng bên phải so trong cùng nhóm ngày: trong thứ 2, giờ hành chính 0,31%, buổi tối 0,64%, gấp 2,1 lần. Trong thứ 3 tới 6, 1,03% so với 1,86%, gấp 1,8 lần. Mức tỉ lệ khác xa nhau nhưng chênh lệch giữ nguyên khoảng 2 lần."

**Chuyển:** "Kiểm tra cuối của phần này: kết quả có phụ thuộc ngưỡng độ phủ không."

### Slide 11 — Độ vững theo ngưỡng · 1:00
**Chỉ vào:** khoảng cách giữa chấm xanh và chấm vàng ở mỗi ngưỡng.

**Lời nói:** "Ngưỡng 0,6 là lựa chọn của nhóm, nên em làm lại ở 5 ngưỡng. Lọc càng chặt thì cả hai khung giờ đều tăng, vì loại bớt nhãn 0 sai, nhưng khoảng cách không đổi: tỉ số luôn quanh 2. Vậy kết luận không phụ thuộc việc chọn ngưỡng."

**Chuyển:** "Đến đây kết quả có vẻ rõ. Nhưng khi tách theo loại video, em thấy một điều quan trọng."

---

## D. Kiểm soát nhiễu

### Slide 12 — Video không thể trending · 1:00
**Lời nói:** "Chart chính Việt Nam gần như không bao giờ có Shorts, tức video dưới 3 phút: chỉ 5 trên 23.093 video. Không có video tin tức nào trong 9.632 video, không có video thể thao nào trong 3.021 video. Điều này khớp với việc YouTube đổi định nghĩa trending từ tháng 7/2025, chỉ lấy video từ bảng âm nhạc, phim và game."

**Chuyển:** "Vậy hai khung giờ có cùng tỉ lệ các loại video này không?"

### Slide 13 — Thành phần video mỗi khung giờ · 1:00
**Chỉ vào:** cặp thanh "Tin tức", "Dài > 10 phút", "Thuộc đợt 2".

**Lời nói:** "Không. So với giờ nghỉ, giờ hành chính có nhiều tin tức hơn, 27% so với 22%; ít video dài hơn, 24,5% so với 31,5%; nhiều Shorts hơn, 61% so với 55%; ít trò chơi và âm nhạc hơn; và nhiều video thuộc đợt có tỉ lệ nền thấp, 48% so với 33%. Cả bốn điểm đều kéo tỉ lệ giờ hành chính xuống. Vì vậy một phần chênh lệch có thể đến từ loại video, chứ không phải giờ đăng."

**Chuyển:** "Cách kiểm tra là so trong cùng loại video."

### Slide 14 — So trong cùng loại video · 1:15
**Chỉ vào:** cặp chấm của Blog, Giải trí; cặp chấm "> 10 phút".

**Lời nói:** "Bên trái, so trong cùng danh mục: Blog và Giải trí, giờ nghỉ vẫn gấp 2,4 lần; Trò chơi gấp 1,5 lần; riêng Âm nhạc ngang nhau. Tin tức, Thể thao gần 0 ở cả hai khung giờ. Bên phải, so trong cùng độ dài: với video trên 10 phút, giờ nghỉ 3,1% so với 2,0%. Chênh lệch nhỏ đi so với 1,9 lần ban đầu, nhưng vẫn còn."

**Chuyển:** "Để gộp tất cả các so sánh này thành một con số, em dùng tỉ số Mantel–Haenszel."

### Slide 15 — Sau kiểm soát · 1:45 (slide quan trọng nhất)
**Chỉ vào:** đi từ trên xuống các chấm đỏ; đường gạch ở 1.

**Lời nói:** "Biểu đồ này kiểm soát tăng dần từng yếu tố. Mỗi hàng là: so giờ nghỉ với giờ hành chính trong từng nhóm video giống nhau về các yếu tố đó, rồi gộp lại. Khoảng tin cậy tính bằng cách lấy mẫu lại theo kênh 300 lần, vì video cùng một kênh không độc lập với nhau.

Chấm đỏ là chart chính. Chưa kiểm soát: 1,91. Thêm ngày đăng và quy mô kênh: gần như không đổi, khoảng 1,8. Thêm danh mục: còn 1,47, khoảng tin cậy từ 1,04 đến 2,02, vẫn nằm hẳn bên phải đường 1. Thêm thời lượng: còn 1,24, và khoảng tin cậy chạm 1.

Nghĩa là khoảng một nửa chênh lệch ban đầu là do loại video. Phần còn lại, khoảng 1,2 tới 1,5 lần, vẫn nghiêng về giờ nghỉ nhưng không còn chắc chắn khi kiểm soát thêm thời lượng.

Chấm xanh là chart danh mục: quanh 1 ở mọi mức, tức không khác biệt."

**Chuyển:** "Một lo ngại nữa là vài kênh lớn tạo ra kết quả này."

### Slide 16 — Không do vài kênh lớn · 1:00
**Chỉ vào:** độ dài các thanh (đều thấp, tối đa 8); bảng bên phải.

**Lời nói:** "Đây là 20 kênh có nhiều video trending nhất. Kênh đứng đầu chỉ có 8 video; 398 video trending đến từ 221 kênh, 10 kênh đầu chỉ chiếm 15%. Khi bỏ dần 5, 10, 20 kênh đầu, tỉ số không giảm mà còn tăng nhẹ từ 1,79 lên 1,91. Vậy kết quả không phải do vài kênh lớn."

**Chuyển:** "Phần tiếp theo mô tả các video đã lọt chart."

---

## E–F. Chân dung video trending và nhãn danh mục

### Slide 17 — Chân dung video trending · 1:00
**Chỉ vào:** cặp thanh "Dài > 10 phút" và "Trò chơi, Âm nhạc"; cặp "Đăng giờ hành chính".

**Lời nói:** "Thanh đỏ là video trending, thanh xám là video thường. 82% video trending dài trên 10 phút, so với 29%. Trò chơi và âm nhạc chiếm 74%, so với 12%. Shorts chỉ hơn 1%, so với 57% ở video thường; tin tức và thể thao bằng 0. Thời lượng trung vị 22 phút so với 2 phút. Khác biệt về giờ đăng, 22% so với 35%, nhỏ hơn nhiều. Loại video quan trọng hơn giờ đăng."

**Chuyển:** "Với video đã lọt chart, giờ đăng có làm lên nhanh hơn không?"

### Slide 18 — Khi đã lọt chart · 0:45
**Chỉ vào:** hai đường tích luỹ gần trùng nhau.

**Lời nói:** "Hai đường gần trùng nhau: một nửa video lên chart trong khoảng 21 tới 25 giờ, ở cả hai khung giờ. Hạng cao nhất cũng gần như nhau. Giờ đăng chỉ liên quan tới chuyện có lọt chart hay không, không liên quan tới tốc độ hay thứ hạng."

**Chuyển:** "Cuối cùng là nhãn thứ hai, chart theo danh mục."

### Slide 19 — Chart danh mục · 1:15
**Chỉ vào:** đoạn đi ngang từ 0,2 (trái); hai chấm Shorts gần nhau (phải).

**Lời nói:** "Bên trái là lý do chọn ngưỡng 0,3 cho nhãn này: dưới 0,2 tỉ lệ thấp vì sót nhãn, từ 0,2 trở lên tỉ lệ đi ngang khoảng 3,2 tới 3,5%, tức là nhãn 0 đã đáng tin. Bên phải: chart danh mục chọn video ngược với chart chính, Shorts lại lọt nhiều nhất, khoảng 3,7%, và hai khung giờ gần nhau. Sau kiểm soát, tỉ số là 0,98, khoảng tin cậy chứa 1: không khác biệt."

**Chuyển:** "Tổng hợp lại, đây là câu trả lời."

---

## I. Kết luận

### Slide 20 — Trả lời câu hỏi · 1:15
**Lời nói:** "Một: với Top Trending chung, đăng ngoài giờ hành chính, rõ nhất là chiều tối ngày thường 16 tới 18 giờ, có lợi thế vừa phải. Thô là 1,9 lần, sau khi kiểm soát còn khoảng 1,2 tới 1,5 lần, và không còn chắc chắn khi kiểm soát thêm thời lượng.

Hai: với top theo danh mục, không có khác biệt.

Ba, và quan trọng nhất: loại video quyết định nhiều hơn giờ đăng. 82% video trending chính dài trên 10 phút, gần như không có Shorts hay tin tức. Đăng đúng giờ không bù được cho việc video không thuộc loại mà chart chính chọn."

**Chuyển:** "Kết luận này đúng trong phạm vi dữ liệu, với các giới hạn sau."

### Slide 21 — Giới hạn · 1:00
**Lời nói:** "Crawler chạy trên máy cá nhân, chỉ có mặt khoảng 59% số giờ; nhóm xử lý bằng lọc độ phủ và bảng độ nhạy. Tập sạch chỉ đến từ 14 ngày, nặng về thứ 2; em đã kiểm soát ngày đăng. Dữ liệu chỉ gồm các kênh nhóm theo dõi. Và quan trọng nhất: đây là dữ liệu quan sát, nên em chỉ nói được giờ nghỉ **đi kèm** tỉ lệ trending cao hơn, chưa chứng minh được đổi giờ đăng sẽ làm video dễ lên trending hơn."

**Chuyển:** "Những phát hiện này định hướng cho Report 4."

### Slide 22 — Đề xuất cho Report 4 · 0:45
**Lời nói:** "Report 4 sẽ dùng Logistic Regression và XGBoost trên tập sạch. Từ EDA: đưa loại video và ngày đăng vào làm feature vì chúng giải thích phần lớn chênh lệch; chỉ khoảng 1% video lọt trending nên dùng class weight và đánh giá bằng PR-AUC; chia train test theo kênh để tránh rò rỉ. Mô hình sẽ cho biết khung giờ còn đóng góp bao nhiêu khi đã có các yếu tố khác. Phần của em xin dừng ở đây."

---

## Chuẩn bị hỏi đáp

| Câu hỏi có thể gặp | Trả lời ngắn | Slide làm bằng chứng |
|---|---|---|
| Vì sao không dùng p-value? | Mục tiêu là mô tả độ lớn chênh lệch; khoảng tin cậy cho thấy cả độ lớn lẫn độ bất định. Report 4 kiểm tra bằng mô hình | 2, 15 |
| 1,9 lần có đáng tin không? | Bị phóng đại bởi loại video; sau kiểm soát còn 1,2–1,5 lần, khoảng tin cậy chạm 1 khi thêm thời lượng | 13, 14, 15 |
| Sao chắc không phải do thứ 2? | So trong cùng nhóm ngày vẫn gấp khoảng 2 lần; kiểm soát ngày đăng gần như không đổi tỉ số | 10, 15 |
| Bỏ video độ phủ thấp có làm lệch không? | Tỉ lệ qua ngưỡng của 2 khung giờ gần bằng nhau; kết quả giống nhau ở mọi ngưỡng | 4, 11 |
| Vì sao khoảng tin cậy ở slide 15 rộng hơn slide 8? | Slide 15 lấy mẫu lại theo kênh, vì video cùng kênh giống nhau; cách này thận trọng hơn | 15 |
| Đỉnh 4 giờ sáng là gì? | 337 video, 14/24 video trending từ 2 kênh livestream (1 blog, 1 âm nhạc): hiệu ứng kênh | 7 |
| Shorts xác định thế nào? | Video ≤ 3 phút, giới hạn Shorts từ 15/10/2024; API không cho biết video dọc hay ngang nên là ước lượng | 6, 12 |
| Vì sao chart chính không có Shorts, tin tức? | YouTube đổi định nghĩa trending từ 07/2025, chỉ lấy từ bảng âm nhạc, phim, game | 12 |
| Vậy nên đăng giờ nào? | Với video dài, game, âm nhạc: chiều tối ngày thường; nhưng chọn đúng loại video quan trọng hơn | 14, 17, 20 |
| Có chứng minh nhân quả không? | Không, dữ liệu quan sát; chỉ nói "đi kèm" | 21 |
