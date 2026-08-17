<p align="center">
  <img src="custom_components/hanet_connect/brand/icon.png" alt="HANET Connect" width="128">
</p>

# HANET Connect cho Home Assistant

Custom integration giúp kết nối tài khoản và camera HANET với Home Assistant.
Đây là dự án cộng đồng, không phải sản phẩm chính thức của HANET.

- **GitHub:** [camera-hanet-connect-home-assistant](https://github.com/trankhanhduy2929-beep/camera-hanet-connect-home-assistant)
- **Báo lỗi:** [GitHub Issues](https://github.com/trankhanhduy2929-beep/camera-hanet-connect-home-assistant/issues)

## Yêu cầu

- Home Assistant `2025.1.0` trở lên.
- Tài khoản HANET đang xem được camera trên ứng dụng HANET Connect.
- URL máy chủ kích hoạt HTTPS và license key do đơn vị cung cấp bản cài gửi.
- Home Assistant có kết nối Internet để đăng nhập, kích hoạt và nhận dữ liệu.

## Cài đặt bằng HACS

[![Mở repository trong HACS](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=trankhanhduy2929-beep&repository=camera-hanet-connect-home-assistant&category=integration)

### Cách 1: Thêm tự động

1. Bấm nút **Mở repository trong HACS** phía trên.
2. Chọn Home Assistant cần cài đặt.
3. Xác nhận thêm repository **HANET Connect**.
4. Chọn **Download**.
5. Khởi động lại Home Assistant.
6. Vào **Settings > Devices & services > Add integration**.
7. Tìm và chọn **HANET Connect**.

### Cách 2: Thêm thủ công

1. Mở **HACS > Integrations**.
2. Mở menu góc trên bên phải, chọn **Custom repositories**.
3. Dán chính xác URL sau:

   ```text
   https://github.com/trankhanhduy2929-beep/camera-hanet-connect-home-assistant
   ```

4. Chọn loại **Integration**, sau đó bấm **Add**.
5. Mở repository **HANET Connect** vừa thêm và chọn **Download**.
6. Khởi động lại Home Assistant.
7. Vào **Settings > Devices & services > Add integration > HANET Connect**.

Repository hiện tải trực tiếp từ nhánh `main`; HACS không cần GitHub Release
hoặc file asset `hanet_connect.zip`.

## Sửa lỗi HACS không download được

Nếu HACS báo:

```text
Downloading trankhanhduy2929-beep/camera-hanet-connect-home-assistant
with version v1.0.0 failed with (Could not download, see log for details)
```

HACS đang giữ cấu hình cũ từng yêu cầu một GitHub Release `v1.0.0`. Thực hiện:

1. Mở **HACS > Integrations**.
2. Xóa repository **HANET Connect** khỏi danh sách đã tải nếu đang tồn tại.
3. Mở **Custom repositories** và xóa URL cũ của repository.
4. Khởi động lại Home Assistant.
5. Thêm lại repository bằng nút HACS hoặc URL chính xác ở trên.
6. Mở repository và chọn **Download** lại.

Nếu vẫn lỗi, mở menu repository trong HACS, chọn **Update information**, sau đó
thử tải lại. Có thể cài thủ công theo phần tiếp theo để sử dụng ngay.

## Cài đặt thủ công

1. Tải ZIP nhánh `main` tại
   [Download source](https://github.com/trankhanhduy2929-beep/camera-hanet-connect-home-assistant/archive/refs/heads/main.zip).
2. Giải nén file vừa tải.
3. Chép nguyên thư mục:

   ```text
   custom_components/hanet_connect
   ```

   vào thư mục cấu hình Home Assistant:

   ```text
   /config/custom_components/hanet_connect
   ```

4. Kiểm tra đường dẫn cuối cùng:

   ```text
   /config/custom_components/hanet_connect/manifest.json
   ```

5. Khởi động lại Home Assistant.
6. Vào **Settings > Devices & services > Add integration > HANET Connect**.

## Kích hoạt và đăng nhập

1. Nhập URL máy chủ kích hoạt HTTPS nếu ô này chưa được điền sẵn.
2. Nhập license key được cung cấp.
3. Nếu màn hình báo đang chờ duyệt, gửi **mã cài đặt** hiển thị trên màn hình
   cho đơn vị cấp license. Sau khi được duyệt, bấm gửi lại để tiếp tục.
4. Nhập tài khoản và mật khẩu HANET.
5. Chờ Home Assistant tải địa điểm, camera, FaceID và sự kiện.

Public signing key dùng để kiểm tra chữ ký license đã được nhúng sẵn trong
integration. Người dùng không cần tải, nhập hoặc chép thêm file sign key.

## Sử dụng

Sau khi cấu hình thành công, Home Assistant tự tạo các entity phù hợp với thiết
bị và quyền của tài khoản, bao gồm camera, ảnh nhận diện, cảm biến, sự kiện,
công tắc, nút bấm, lựa chọn và cập nhật firmware.

- Mở camera entity để xem ảnh hoặc luồng trực tiếp P2P.
- Mở trang thiết bị HANET để xem toàn bộ entity của từng camera.
- Sự kiện nhận diện mới được phát trên event bus với tên
  `hanet_connect_event`.
- Các action nâng cao nằm trong **Developer tools > Actions** với tiền tố
  `hanet_connect`.

Ví dụ lắng nghe sự kiện nhận diện:

```yaml
triggers:
  - trigger: event
    event_type: hanet_connect_event
actions:
  - action: persistent_notification.create
    data:
      title: HANET
      message: "{{ trigger.event.data }}"
```

Ví dụ gửi lệnh mở cửa:

```yaml
action: hanet_connect.send_command
data:
  device_id: "HANET_DEVICE_ID"
  command: open_door
```

Chỉ dùng các lệnh điều khiển với thiết bị mà bạn có quyền quản lý.

## Cập nhật

### Cài bằng HACS

1. Mở **HACS > Integrations > HANET Connect**.
2. Mở menu repository và chọn **Update information**.
3. Chọn bản cập nhật mới nhất rồi khởi động lại Home Assistant.

### Cài thủ công

1. Tải lại ZIP nhánh `main` từ liên kết **Download source**.
2. Ghi đè thư mục `/config/custom_components/hanet_connect` bằng thư mục mới.
3. Khởi động lại Home Assistant.

Không xóa config entry trước khi cập nhật; cấu hình và entity hiện tại sẽ được
Home Assistant giữ lại.

## Xử lý sự cố

### Không tìm thấy integration

- Kiểm tra đúng đường dẫn
  `/config/custom_components/hanet_connect/manifest.json`.
- Xóa thư mục bị lồng hai lần như
  `custom_components/hanet_connect/hanet_connect`.
- Khởi động lại toàn bộ Home Assistant, không chỉ tải lại YAML.
- Làm mới trình duyệt nếu giao diện vẫn giữ cache cũ.

### Không kích hoạt được license

- Kiểm tra URL máy chủ bắt đầu bằng `https://` và không có khoảng trắng.
- Kiểm tra Home Assistant có Internet và ngày giờ hệ thống chính xác.
- Kiểm tra license key được nhập đầy đủ.
- Nếu license đang chờ duyệt, bị khóa, hết hạn hoặc đã đủ số máy, liên hệ đơn vị
  cấp license và gửi mã cài đặt đang hiển thị.

### Không đăng nhập được HANET

- Kiểm tra lại tài khoản và mật khẩu trên ứng dụng HANET Connect.
- Nếu vừa đổi mật khẩu, mở integration và chọn **Reconfigure** để nhập lại.
- Đảm bảo tài khoản đang được chia sẻ đúng địa điểm và camera cần sử dụng.

### Không thấy camera hoặc không xem được live

- Mở ứng dụng HANET Connect để kiểm tra camera vẫn online và tài khoản còn quyền.
- Chờ một phút rồi tải lại integration trong **Devices & services**.
- Đóng các phiên xem live cũ trước khi mở lại camera.
- Xem log Home Assistant và tìm từ khóa `hanet_connect` nếu lỗi tiếp tục xảy ra.

## Gỡ cài đặt

1. Vào **Settings > Devices & services > HANET Connect** và xóa config entry.
2. Gỡ integration trong HACS hoặc xóa thư mục
   `/config/custom_components/hanet_connect`.
3. Khởi động lại Home Assistant.

## Bảo mật và quyền riêng tư

- Không chia sẻ license key, mật khẩu HANET hoặc file backup Home Assistant.
- Chỉ cài repository và bản phát hành từ nguồn mà bạn tin cậy.
- Kiểm tra nội dung diagnostics trước khi đăng công khai.
- Chỉ sử dụng integration với tài khoản và thiết bị mà bạn có quyền truy cập.
