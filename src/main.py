# -*- coding: utf-8 -*-
# @Time    : 2022/5/22 19:56
# @Author  : CYX
# @Email   : im.cyx@foxmail.com
# @File    : main.py
# @Software: PyCharm
# @Project : UESTC_Report

import os
import cv2
import numpy as np
import base64
import re
import json
import requests
from time import sleep, strftime
from selenium import webdriver
from selenium.webdriver import ActionChains
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait

config_path = './src/config.json'

class CalcSliderDist:
    def __init__(self, template_src, target_src):
        self.target_src = target_src
        self.template_src = template_src

        self.base_path = './temp'
        if not os.path.exists(self.base_path):
            os.mkdir(self.base_path)

        self.template_src_dir = os.path.join(self.base_path, "template_src.png")
        self.template_gray_dir = os.path.join(self.base_path, "template_gray.jpg")
        self.target_src_dir = os.path.join(self.base_path, "target_src.png")
        self.target_gray_dir = os.path.join(self.base_path, "target_gray.jpg")
        self.final_res_dir = os.path.join(self.base_path, "final_res.jpg")

    def Base64Decode(self, src_info, filename):
        im_base64 = re.search("data:image/(?P<ext>.*?);base64,(?P<data>.*)", src_info, re.DOTALL)
        if im_base64:
            ext = im_base64.groupdict().get("ext")
            data = im_base64.groupdict().get("data")
            img = base64.urlsafe_b64decode(data)
            with open(filename, "wb") as f:
                f.write(img)
        else:
            print("Do not parse!")

    def process(self):
        sleep(5)
        # Base64解码
        self.Base64Decode(self.target_src, self.target_src_dir)
        self.Base64Decode(self.template_src, self.template_src_dir)

        # 读取保存的图片
        target = cv2.imread(self.target_src_dir, 0)
        template = cv2.imread(self.template_src_dir, 0)
        cv2.imwrite(self.target_gray_dir, target)
        target = cv2.imread(self.target_gray_dir)

        # 因为图像有空白背景，二值化并将滑块图像裁剪，删除空白背景
        _, imgss = cv2.threshold(target, 127, 255, cv2.THRESH_BINARY)
        cnts = cv2.findContours(imgss[:,:,0], cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)[-2]
        cnt = sorted(cnts, key=cv2.contourArea)[-1]
        x,y,w,h = cv2.boundingRect(cnt)
        target = target[y:y+w,x:x+h]

        # 如果图像较亮，将滑块亮度降低增加匹配准确率
        if template.mean()>100:
            acc = np.ones_like(target)*int(template.mean()-100)
            target -= acc

        cv2.imwrite(self.template_gray_dir, template)
        cv2.imwrite(self.target_gray_dir, target)
        target = cv2.imread(self.target_gray_dir)
        template = cv2.imread(self.template_gray_dir)
        # 比较匹配区域
        result = cv2.matchTemplate(target, template, cv2.TM_CCOEFF_NORMED)
        x, y = np.unravel_index(result.argmax(), result.shape)
        # 展示圈出来的区域
        cv2.rectangle(template, (y, x), (y + w, x + h), (7, 249, 151), 2)
        cv2.imwrite(self.final_res_dir, template)
        # 保存最终结果位置
        dist = y/template.shape[1]

        return dist


class AutomaticReport:
    def __init__(self, configs):
        """
        装载配置参数
        :param configs: 外部文件的配置参数
        """
        # 延时信息设置
        delay_time = configs['delay_time']
        self.implicitly_wait = delay_time["implicitly_wait_time"]
        self.detect_slider_wait = delay_time["detect_slider_wait_time"]
        self.login_complete_wait = delay_time["login_complete_wait_time"]
        self.login_complete_interval = delay_time["login_complete_interval_time"]
        self.page_load_wait = delay_time["page_load_wait_time"]
        self.page_load_interval = delay_time["page_load_interval_time"]
        self.simulate_slide_down_interval = delay_time["simulate_slide_down_interval_time"]
        self.submit_click_wait = delay_time["submit_click_wait_time"]
        self.confirm_click_wait = delay_time["confirm_click_wait_time"]
        self.switch_page_wait = delay_time["switch_page_wait_time"]
        self.crawl_results_wait = delay_time["crawl_results_wait_time"]
        self.quit_wait = delay_time["quit_wait_time"]

        # 最大尝试次数
        self.slider_try_num = configs['slider_try_num']
        self.query_try_num = configs['query_try_num']

        # 页面网址
        self.Temperature_index = configs['Temperature_index']
        self.Info_index = configs['Info_index']

        # 在线配置，从私有环境变量读取账号密码
        if configs['online']:
            deployment = configs['online_deployment']

            # 账号密码
            secrets = os.environ.get("LOGIN")
            if secrets is None:
                raise Exception("Sorry <( _ _ )> ！Account & Password not provided")
            else:
                secret = secrets.split("#")
                self.account = secret[0]
                self.password = secret[1]
            # geckodriver地址(在线无需配置)
            self.geckodriver_path = None
            # 飞书通知信息
            if configs['feishu_info']:
                self.webhook_url = os.environ.get("NOTICE")
                if self.webhook_url is None:
                    raise Exception("Sorry <( _ _ )> ！Webhook link not provided")
                self.repository_url = os.environ.get("REPOSITORY")

        # 离线配置，直接读取账号密码
        else:
            deployment = configs['offline_deployment']

            # 账号密码
            self.account = deployment['account']
            self.password = deployment['password']
            if not self.account and self.password:
                raise Exception("If set offline deployment, please input your account and password information!")
            # geckodriver地址
            self.geckodriver_path = deployment['geckodriver_path']
            if self.geckodriver_path is None:
                raise Exception("If set offline deployment, please input your geckodriver path!")
            # 飞书通知信息
            if configs['feishu_info']:
                self.webhook_url = deployment['webhook_url']
                if self.webhook_url is None:
                    raise Exception("If enable notification, please input your webhook link which generated in Feishu!")
                self.repository_url = deployment['repository_url']

        # 浏览器自动化参数配置
        self.options = webdriver.FirefoxOptions()
        if deployment['use_headless']:
            self.options.add_argument("--headless")  # linux必须设置火狐为headless无头执行
        if deployment['use_gpu']:
            self.options.add_argument("--disable-gpu")

        # 飞书报文信息
        self.msg_content = configs['msg_content']
        self.msg_headers = configs['msg_headers']

        # webdriver设置
        if self.geckodriver_path:
            self.driver = webdriver.Firefox(service=Service(self.geckodriver_path), options=self.options)
        else:
            self.driver = webdriver.Firefox(options=self.options)

    def login(self):
        """
        登陆部分实现
        :return: None
        """
        # 打开登陆页面
        self.driver.implicitly_wait(self.implicitly_wait)
        self.driver.get(self.Temperature_index)

        # 定位并输入账号密码，然后点击登录
        self.driver.find_element(By.ID, 'username').send_keys(self.account)
        self.driver.find_element(By.ID, 'password').send_keys(self.password)
        self.driver.find_element(By.XPATH, "//button[1]").click()
        sleep(self.detect_slider_wait)

        # 滑块失败计数
        err_sum = 0
        # 持续通过滑块
        while True:
            # 滑块子界面出现，定位target和template位置，处理
            src1 = self.driver.find_element(By.ID, 'img1').get_attribute("src")
            src2 = self.driver.find_element(By.ID, 'img2').get_attribute("src")
            # 解码base64编码的滑块和模板信息，获得移动距离信息
            dist = CalcSliderDist(src1, src2).process()

            # 模拟起点按住滑块->滑动滑块->缺口松滑块
            width = 280
            button = self.driver.find_element(By.CLASS_NAME, 'slider')
            action = ActionChains(self.driver)
            action.click_and_hold(button)
            action.move_by_offset(int(dist * width), 0)
            action.release()
            action.perform()

            # 等待登陆成功登录界面消失
            try:
                WebDriverWait(self.driver, self.login_complete_wait, self.login_complete_interval).until_not(
                    EC.presence_of_element_located((By.ID, 'card-header')))
                print(0000)
            # 登陆界面存在，滑块未成功，继续滑块尝试
            except Exception as err:
                err_sum += 1
                # 连续过8次不入，则抛出异常
                if err_sum > self.slider_try_num:
                    self.driver.quit()
                    raise Exception(err, '\nFailure times over %d, break!' % self.slider_try_num)
                else:
                    continue
            # 等待签到界面加载完成
            finally:
                while True:
                    WebDriverWait(self.driver, self.page_load_wait, self.page_load_interval).until(
                        EC.presence_of_element_located((By.XPATH, '//div[@class="mint-cell-group-title"]')))
                    break
                break

    def signin(self):
        """
        打卡签到部分实现
        :return: None
        """
        # 进入打卡页面，模拟手动下滑
        btn_submit = "//button[@class='mint-button mt-btn-primary mint-button--large']"
        btn_confirm = "//button[@class='mint-msgbox-btn mint-msgbox-confirm mt-btn-primary']"
        for i in range(6):
            ActionChains(self.driver).send_keys(Keys.PAGE_DOWN)
            sleep(self.simulate_slide_down_interval)

        # 模拟提交->确认
        sleep(self.submit_click_wait)
        self.driver.find_element(By.XPATH, btn_submit).click()
        sleep(self.confirm_click_wait)
        self.driver.find_element(By.XPATH, btn_confirm).click()

    def query(self):
        """
        查询打卡结果实现
        :return: 打卡结果
        """
        # 结果抓取失败计数
        err_sum = 0
        # 持续抓取结果
        while True:
            # 新标签页查看打卡结果
            self.driver.execute_script(f'window.open("{self.Info_index}");')
            # 打开结果界面，抓取最近打卡结果
            sleep(self.switch_page_wait)
            self.driver.switch_to.window(self.driver.window_handles[-1])
            # 抓取并显示打卡结果，如果页面为空就在新标签页刷新取结果
            sleep(self.crawl_results_wait)
            s = self.driver.find_elements(By.XPATH, "//div[@class='mint-layout-container bh-bg-color-light sjaku1g03']")
            if s:
                break
            else:
                err_sum += 1
                if err_sum > self.query_try_num:
                    break

        # 整理结果
        final_res = ''
        for res in s:
            final_res += res.text.replace('\n', '\t') + '\n'

        return final_res

    def quit(self):
        """
        退出 driver
        :return: None
        """
        # 延时退出
        sleep(self.quit_wait)
        self.driver.quit()

    def notification_feishu(self, text):
        """
        飞书通知
        :param text: 打卡结果
        :return: None
        """
        self.msg_content["card"]["elements"][0]["text"]["content"] = text
        self.msg_content["card"]["elements"][1]["actions"][0]["text"]["content"] = "查看Actions结果 :惊喜:"
        self.msg_content["card"]["elements"][1]["actions"][0]["url"] = self.repository_url
        self.msg_content["card"]["header"]["title"]["content"] = "打卡结果通报：%s" % strftime("%H:%M:%S")

        res = requests.post(self.webhook_url, json.dumps(self.msg_content), headers=self.msg_headers)

        print(res)


def main():
    # 加载配置信息
    with open(config_path, 'r') as f:
        configs = json.load(f)

    # 启动逻辑
    Report = AutomaticReport(configs)
    # 通过身份认证登录界面
    Report.login()
    # 打卡
    Report.signin()
    # 查询结果
    final_res = Report.query()
    # 飞书推送结果
    Report.notification_feishu(final_res)
    # 退出
    Report.quit()


if __name__ == '__main__':
    main()