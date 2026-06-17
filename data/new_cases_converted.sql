-- 文件名：用户是否抄表
SELECT

	o1.NAME AS 供电单位,

	cons_no 用户户号,

	cons_name 用户名称,

	c.mr_sect_no 抄表段,

	rs1.NAME AS 抄表段名称,

	roa1.operator_no AS 抄表员,

	elec_addr 用电地址,

	p3.NAME AS 用户状态,

	p2.NAME AS 用户分类,

	p1.NAME AS 费控分类

FROM

	m_c_cons c


LEFT JOIN ac_org o1 ON o1.id = c.org_no
LEFT JOIN m_r_sect rs1 ON id = c.mr_sect_no AND effect_flag = 1
LEFT JOIN m_r_oper_activity roa1 ON roa1.mr_sect_no = c.mr_sect_no AND effect_flag = 1 AND roa1.act_code = '03'
LEFT JOIN m_p_code p3 ON code_type = 'statusCode' AND VALUE = c.status_code AND take_effect_flag = 1
LEFT JOIN m_p_code p2 ON code_type = 'custSortCode' AND VALUE = c.cons_sort_code AND take_effect_flag = 1
LEFT JOIN m_p_code p1 ON code_type = 'ctlMode' AND VALUE = c.ctl_mode AND take_effect_flag = 1
WHERE

	c.org_no ={供电单位}

	AND c.status_code <> '9'

	AND NOT EXISTS (

	SELECT

		1

	FROM

		m_e_cons_snap_arc a

	WHERE

		a.cons_no = c.cons_no

		AND a.ym ={电费年月}

		AND a.org_no = c.org_no

	)

	AND NOT EXISTS (

	SELECT

		1

	FROM

		m_e_cons_snap b

	WHERE

		b.cons_no = c.cons_no

		AND b.ym ={电费年月}

	AND b.org_no = c.org_no

	)

-- 文件名：欠费冻结时间查询
SELECT

	  a.orgname '县公司',a.`name` '供电所',a.cons_name '用户名称',a.cons_no '用户编号',a.rcvbl_ym '应收年月',a.rcvbl_amt '应收电费',a.rcved_amt '实收电费',a.qf '欠费'

FROM

	(

	SELECT

		a.rcvbl_ym,

	  c.cons_no,

		c.cons_name,

		o.`name`,

		o1.`name` orgname,

		ifnull(a.rcvbl_amt,0) rcvbl_amt,

		ifnull(a.rcved_amt,0) y_rcved_amt,

		ifnull(sum(b.this_rcved_amt),0) this_rcved_amt,

		ifnull(a.rcved_amt,0)-ifnull(sum(b.this_rcved_amt),0) rcved_amt,

		ifnull(a.rcvbl_amt,0) - ifnull(a.rcved_amt,0) +ifnull(sum(b.this_rcved_amt),0) qf

	FROM

		m_a_rcvbl_flow a

		left JOIN m_a_rcved_flow b ON a.id = b.rcvbl_amt_id  and b.create_time > {截止时间}

		LEFT JOIN m_c_cons c on c.cons_no = a.cons_no

		left join ac_org o on c.org_no = o.id

		left join ac_org o1 on left(c.org_no,7) = o1.id

	WHERE

		a.rcvbl_ym =  {应收年月}

		and a.org_no LIKE concat({组织},'%') and c.org_no LIKE concat({组织},'%')

		GROUP BY a.id

		UNION ALL

	SELECT

		a.rcvbl_ym,

		c.cons_no,

		c.cons_name,

		o.`name`,

		o1.`name` orgname,

		ifnull(a.rcvbl_amt,0) rcvbl_amt,

		ifnull(a.rcved_amt,0) y_rcved_amt,

		ifnull(sum(b.this_rcved_amt),0) this_rcved_amt,

		ifnull(a.rcved_amt,0)-ifnull(sum(b.this_rcved_amt),0) rcved_amt,

		ifnull(a.rcvbl_amt,0) - ifnull(a.rcved_amt,0) +ifnull(sum(b.this_rcved_amt),0) qf

	FROM

		m_a_rcvbl_flow_arc a

		left JOIN m_a_rcved_flow b ON a.id = b.rcvbl_amt_id  and b.create_time > {截止时间}

		LEFT JOIN m_c_cons c on c.cons_no = a.cons_no

		left join ac_org o on c.org_no = o.id

		left join ac_org o1 on left(c.org_no,7) = o1.id

	WHERE

		a.create_time > {开始时间}

		and a.rcvbl_ym =  {应收年月}

		and a.org_no LIKE concat({组织},'%') and c.org_no LIKE concat({组织},'%')

		GROUP BY a.id

		) a WHERE a.qf > 0

-- 文件名：抄表方式查询
select

  o1.name AS 单位名称,

	a.cons_no 用户编号,

	a.cons_name 用户名称,

	a.elec_addr 用电地址,

	b.mp_id 计量点编号,

	b.made_no 出厂编号,

  date_format(b.this_ymd,'%Y-%m-%d') 抄表日期,

  p3.name AS 示数类型,

	b.last_mr_num 上次示数,

	b.this_read 本次示数,

	b.t_factor 综合倍率,

	b.last_mr_pq 上次抄见电量,

	b.this_read_pq 本次抄见电量,

  p2.name AS 抄表方式,

  p1.name AS 抄表状态,

  tq.tg_name 台区名称,

  line.line_name 线路名称

 from m_e_cons_snap_arc a

 join m_r_data_arc b on a.id=b.calc_id

 join m_c_mp c on c.id=b.mp_id

 left join m_g_tg tq on tq.id=c.tg_id

 left join m_g_line line on line.id=c.line_id


LEFT JOIN ac_org o1 ON id=a.org_no
LEFT JOIN m_p_code p3 ON p3.code_type ='readTypeCode' and p3.value=b.read_type_code AND take_effect_flag = 1
LEFT JOIN m_p_code p2 ON p2.code_type='mrModeCode' and p2.value=b.actual_mode AND take_effect_flag = 1
LEFT JOIN m_p_code p1 ON p1.code_type='mrStatusCode' and value=b.mr_status_code AND take_effect_flag = 1
where a.org_no LIKE concat({组织}, '%') and a.ym={电费年月}

 and EXISTS (select 1 from m_r_plan_arc where app_no=a.app_code and plan_status='10')

 and b.made_no is not null

 and if(({抄表方式} is null or {抄表方式}=''),(1=1),(b.actual_mode={抄表方式}))

 and if(({抄表段编号} is null or {抄表段编号}=''),(1=1),(a.mr_sect_no={抄表段编号}))

 and if(({台区名称} is null or {台区名称}=''),(1=1),(tq.tg_name LIKE concat('%',{台区名称}, '%')))

 and if(({线路名称} is null or {线路名称}=''),(1=1),(line.line_name LIKE concat('%',{线路名称}, '%')))

 and if(({户名} is null or {户名}=''),(1=1),a.cons_name like CONCAT('%',{户名},'%'))

 and if(({户号} is null or {户号}=''),(1=1),a.cons_no like CONCAT('%',{户号},'%'))

 and if(({抄表状态} is null or {抄表状态}=''),(1=1),(b.mr_status_code={抄表状态}))

 ORDER BY a.org_no,a.cons_no,a.cons_name

-- 文件名：用户计量点电价表计
select cons.org_no 单位编码,org.`name` 单位名称,cons.cons_no 用户编号,cons.cons_name 用户名称

	,p3.`name` 用户状态,p1.`name` 用电类别,p9.`name` 行业分类,p2.`name` 费控类型

	,mp.mp_no 计量点,p4.`name` 计量点状态,p5.`name` 计量点分类,p8.`name` 电量计算方式

	,consprc.prc_code 电价码,catprc.cat_prc_name 电价名称

	,p6.`name` 电价用电类别,p10.`name` 电价行业类别,p7.`name` 电价版本用电类别

	,cm.asset_no 资产编号,cm.made_no 表号,p11.`name` 参考表

	,p12.`name` 执行水期,p13.`name` 执行峰谷

from m_c_cons cons

join ac_org org on cons.org_no=org.id

join m_c_sp sp on cons.id=sp.cons_id

join m_c_mp mp on sp.id=mp.sp_id

join m_c_cons_prc consprc on mp.tariff_id=consprc.id

left join m_e_cat_prc catprc on consprc.prc_code=catprc.prc_code and catprc.para_vn=f_get_curver_para_vn(1,left({组织},7))

left join m_c_meter_mp_rela cmmr on mp.id=cmmr.mp_id

left join m_c_meter cm on cmmr.meter_id=cm.id

left join m_p_code p1 on p1.code_type='elecTypeCode' and p1.`value`=cons.elec_type_code

left join m_p_code p2 on p2.code_type='ctlMode' and p2.`value`=cons.ctl_mode

left join m_p_code p3 on p3.code_type='statusCode' and p3.`value`=cons.status_code

left join m_p_code p4 on p4.code_type='mpStatus' and p4.`value`=mp.status_code

left join m_p_code p5 on p5.code_type='mpSortCode' and p5.`value`=mp.type_code

left join m_p_code p6 on p6.code_type='elecTypeCode' and p6.`value`=consprc.elec_type_code

left join m_p_code p7 on p7.code_type='elecTypeCode' and p7.`value`=catprc.elec_type_code

left join m_p_code p8 on p8.code_type='calcMode' and p8.`value`=mp.calc_mode

left join m_p_code p9 on p9.code_type='tradeCode' and p9.`value`=cons.trade_code

left join m_p_code p10 on p10.code_type='tradeCode' and p10.`value`=consprc.trade_code

left join m_p_code p11 on p11.code_type='ynJudgeFlag' and p11.`value`=cm.ref_meter_flag

left join m_p_code p12 on p12.code_type='ynJudgeFlag' and p12.`value`=consprc.fe_flag

left join m_p_code p13 on p13.code_type='ynJudgeFlag' and p13.`value`=consprc.ts_flag

where cons.org_no like concat({组织},'%')

	and cons.status_code<>'9'

	and mp.status_code in('01','02')

order by cons.org_no,cons.cons_no,mp.mp_no

-- 文件名：应收收入查询
select

d.name '供电单位' ,a.rcvbl_ym '电费年月',

a.cons_no '用户编号',c.cons_name '用户名称',c.elec_addr '用电地址',

f.name '供电电压',

g.name '用电类别',

a.mr_sect_no '抄表段编号',

h.name '抄表段名称',

i.name '电费类型',

j.name '费控类型',

a.t_pq '电量',rcvbl_amt '应收电费',rcvbl_inprice_amt '应收价内电费', rcvbl_pl_amt '应收代征电费' ,

IF({线路编号} ='',(SELECT line_name FROM m_g_line WHERE id = (SELECT mp.line_id  FROM m_e_mp_para_snap_arc para,m_c_mp mp


LEFT JOIN m_g_line gl1 ON line_no={线路编号}
WHERE para.calc_id=a.calc_id AND para.mp_id =mp.id ORDER BY mp.mp_sn DESC LIMIT 1)),gl1.line_name) '线路名称',

IF({线路编号} ='',(SELECT line_no FROM m_g_line WHERE id = (SELECT mp.line_id  FROM m_e_mp_para_snap_arc para,m_c_mp mp

WHERE para.calc_id=a.calc_id AND para.mp_id =mp.id ORDER BY mp.mp_sn DESC LIMIT 1)),{线路编号}) '线路编号'

from(

select flow.mr_sect_no,flow.rcvbl_ym,flow.calc_id,flow.cons_no,flow.amt_type,flow.t_pq,flow.rcvbl_amt,

flow.rcvbl_inprice_amt,flow.rcvbl_pl_amt ,flow.elec_type_code,flow.ctl_mode,flow.org_no

from m_a_rcvbl_flow flow where flow.rcvbl_ym={年月} and flow.org_no like concat({组织},'%')

AND EXISTS (SELECT 1 FROM m_e_mp_para_snap_arc mp , m_g_line ml WHERE  flow.calc_id  = mp.calc_id

AND ml.id = mp.line_id  and  if({线路编号}='',(1=1),ml.line_no={线路编号}))

union all

select flow.mr_sect_no,flow.rcvbl_ym,flow.calc_id,flow.cons_no,flow.amt_type,flow.t_pq,flow.rcvbl_amt,

flow.rcvbl_inprice_amt,flow.rcvbl_pl_amt ,flow.elec_type_code,flow.ctl_mode,flow.org_no

from m_a_rcvbl_flow_arc flow where flow.rcvbl_ym={年月} and flow.org_no like concat({组织},'%')

AND EXISTS  (SELECT 1 FROM m_e_mp_para_snap_arc mp , m_g_line ml WHERE  flow.calc_id  = mp.calc_id

AND ml.id = mp.line_id  and if({线路编号}='',(1=1),ml.line_no={线路编号}))

)a

left join m_c_cons c on  c.org_no like concat({组织},'%')  and c.cons_no=a.cons_no

left join ac_org d on a.org_no=d.id

left join m_p_code f on f.code_type='psVoltCode' and f.value=c.volt_code

left join m_p_code g on g.code_type='elecTypeCode' and g.value=a.elec_type_code

left join m_r_sect h on h.id=a.mr_sect_no

left join m_p_code i on i.code_type='paTypeCode' and i.value=a.amt_type

left join m_p_code j on j.code_type='ctlMode' and j.value=a.ctl_mode

-- 文件名：公安-电力用户信息
select a.cons_no '用户编号',a.cons_name '用户名称',crt2.cert_name AS 证件类型',crt1.cert_no AS 证件号码',

cct1.ifnull(mobile,office_tel) AS 联系电话',a.elec_addr '用电地址',o1.name AS 供电单位',null '缴费号',a.mr_sect_no '抄表段编号',

p3.name AS 用电类别',p2.name AS 用户状态',

p1.name AS 供电电压',a.build_date '开户时间'

from (select * from m_c_cons where status_code<>9 and org_no like concat({组织},'%') )a

left join m_c_cons_cert_rela b on a.id=b.cons_id

left join m_c_cons_contact_rela c on a.id=c.cons_id

left join m_c_payment_rela d on a.id=d.cons_id

LEFT JOIN m_c_cert crt2 ON id=b.cert_id
LEFT JOIN m_c_cert crt1 ON id=b.cert_id
LEFT JOIN m_c_contact cct1 ON id=c.contact_id
LEFT JOIN ac_org o1 ON id=a.org_no
LEFT JOIN m_p_code p3 ON code_type='elecTypeCode' and value=a.elec_type_code AND take_effect_flag = 1
LEFT JOIN m_p_code p2 ON code_type='statusCode' and value=a.status_code AND take_effect_flag = 1
LEFT JOIN m_p_code p1 ON code_type='psVoltCode' and value=a.volt_code AND take_effect_flag = 1

-- 文件名：公安-电力缴费信息
select a.cons_no '用户编号',b.cons_name '用户名称' ,

crt1.cert_no AS 证件号码',

cct1.ifnull(mobile,office_tel) AS 联系电话',

b.elec_addr '用电地址',

p2.name AS 用电类别',

a.t_pq '总结算电量',null '缴费号',b.orgn_cons_no '原户号', e.prc_value '电价',

 e.prc_name '电价名称',

 p1.name AS 供电电压',

 a.rcvbl_amt '总结算电费',a.release_date '计算日期', a.release_date '发行日期',

f.rcved_ym '缴费月份',

o1.name AS 供电单位',

a.mr_sect_no '抄表段编号'

from

 (select * from m_a_rcved_flow where org_no like concat({组织},'%')  and rcved_ym={年月})f

 inner join

(

select id,t_pq,rcvbl_amt,calc_id,cons_no,mr_sect_no,release_date,rcvbl_ym from m_a_rcvbl_flow where  org_no like concat({组织},'%') and rcved_amt is not null

union all

select id,t_pq,rcvbl_amt,calc_id,cons_no,mr_sect_no,release_date,rcvbl_ym from m_a_rcvbl_flow_arc where org_no like concat({组织},'%') and rcved_amt is not null

) a on a.id=f.rcvbl_amt_id

inner join m_c_cons b on b.org_no  like concat({组织},'%')  and a.cons_no=b.cons_no

inner join (select calc_id,group_concat(distinct hb.cat_prc_name) prc_name,group_concat(distinct hc.kwh_prc)  prc_value from m_e_cons_prc_amt_arc ha,m_e_cat_prc hb,m_e_kwh_amt_arc hc


LEFT JOIN m_c_cert crt1 ON id=c.cert_id
LEFT JOIN m_c_contact cct1 ON id=f.contact_id
LEFT JOIN m_p_code p2 ON code_type='elecTypeCode' and value=b.elec_type_code AND take_effect_flag = 1
LEFT JOIN m_p_code p1 ON code_type='psVoltCode' and value=b.volt_code AND take_effect_flag = 1
LEFT JOIN ac_org o1 ON id=b.org_no
where  ha.org_no like concat({组织},'%')  and ha.prc_code=hb.prc_code and ha.para_vn=hb.para_vn

and ha.org_no like concat(hb.org_no,'%') and ha.level_num=1

and ha.org_no=hc.org_no and ha.id=hc.prc_amt_id and hc.prc_ts_code='03'

group by ha.calc_id

)e on a.calc_id=e.calc_id

left join m_c_cons_cert_rela c on c.cons_id=b.id

left join m_c_cons_contact_rela f on b.id=f.cons_id

-- 文件名：实收电费明细查询
select o.name 组织机构,b.cons_no 用户编号,c.cons_name 用户名称, b.rcvbl_ym 电费年月,DATE_FORMAT(pf.charge_date, '%Y-%m-%d %H:%i:%s') 收费时间,b.this_rcved_amt 实收电费

                    from m_a_pay_flow pf left join m_a_rcved_flow b on b.charge_id = pf.id

										left join m_c_cons c on b.cons_no = c.cons_no and c.org_no like concat({供电单位}, '%')

										left join ac_org o on b.org_no = o.`code`

                    where  pf.org_no like concat({供电单位}, '%')  and b.rcvbl_ym between {电费年月起} and {电费年月止} and pf.charge_date between {收费时间起} and {收费时间止}

-- 文件名：实收清单-按应收月
select  o1.name AS 供电单位',a.mr_sect_no '抄表段编码',a.cons_no '用户编码' ,b.cons_name '用户名称',c.mr_username '抄表员', a.rcvbl_ym '应收年月',

a.t_pq '应收电量',a.rcvbl_amt '应收电费',a.rcved_amt '实收电费',a.rcvbl_amt-a.rcved_amt '欠费',

e.name '结清状态'

from m_a_rcvbl_flow a,m_c_cons b,(

select  d.cons_no, substring_index(group_concat(distinct e.create_user),',',1) create_user,substring_index(group_concat(distinct f.user_name),',',1) mr_username from m_r_data_arc d,m_r_plan_arc e,ac_user f where d.mr_plan_no=e.id and e.create_user=f.id

and d.org_no like concat({组织},'%')  and d.amt_ym={年月}

group by  d.cons_no

) c,m_p_code e,(select distinct rcvbl_amt_id from m_a_rcved_flow where  org_no  like concat({组织},'%')   and rcvbl_ym={年月}) f


LEFT JOIN ac_org o1 ON code=a.org_no
where a.cons_no=b.cons_no and a.cons_no=c.cons_no  and e.code_type='settleFlag' and a.settle_flag=e.value

and a.org_no  like concat({组织},'%')   and a.rcvbl_ym={年月}

and a.id =f.rcvbl_amt_id

and (a.cons_no={用户编号}   or a.mr_sect_no ={抄表段编号} or c.mr_username ={抄表员姓名} or 1= case when (length({用户编号})+length({抄表段编号})+length({抄表员姓名}))=0  then 1 else 0 end

)

union all

select  (select name from ac_org where code=a.org_no) '供电单位',a.mr_sect_no '抄表段编码',a.cons_no '用户编码' ,b.cons_name '用户名称',c.mr_username '抄表员', a.rcvbl_ym '应收年月',

a.t_pq '应收电量',a.rcvbl_amt '应收电费',a.rcved_amt '实收电费',a.rcvbl_amt-a.rcved_amt '欠费',

e.name '结清状态'

from m_a_rcvbl_flow_arc a,m_c_cons b,(

select  d.cons_no, substring_index(group_concat(distinct e.create_user),',',1) create_user,substring_index(group_concat(distinct f.user_name),',',1) mr_username from m_r_data_arc d,m_r_plan_arc e,ac_user f where d.mr_plan_no=e.id and e.create_user=f.id

and d.org_no like concat({组织},'%')  and d.amt_ym={年月}

group by  d.cons_no

) c,m_p_code e,(select distinct rcvbl_amt_id from m_a_rcved_flow where  org_no  like concat({组织},'%')   and rcvbl_ym={年月}) f

where a.cons_no=b.cons_no and a.cons_no=c.cons_no   and e.code_type='settleFlag' and a.settle_flag=e.value

and a.org_no  like concat({组织},'%')   and a.rcvbl_ym={年月}

and a.id =f.rcvbl_amt_id

and (a.cons_no={用户编号}   or a.mr_sect_no ={抄表段编号} or c.mr_username ={抄表员姓名} or 1= case when (length({用户编号})+length({抄表段编号})+length({抄表员姓名}))=0  then 1 else 0 end

)

-- 文件名：总欠费冻结时间查询
select x.`name` 公司名称,o.`name` 单位名称,ta.cons_no 用户编号,a.cons_name 用户名称,ta.rcvbl_ym 应收年月,ta.release_date 发行日期

  ,ta.rcvbl_amt 应收电费,ta.rcved_amt 实收电费,ta.qf 欠费

from (

  select a.id,a.org_no,a.cons_no,a.rcvbl_ym,a.release_date

    ,a.rcvbl_amt,a.rcved_amt-ifnull(t.this_rcved_amt,0) rcved_amt

    ,a.rcvbl_amt-(a.rcved_amt-ifnull(t.this_rcved_amt,0)) qf

  from m_a_rcvbl_flow a

  left join (

    select a.id,sum(this_rcved_amt) this_rcved_amt

    from m_a_rcvbl_flow a

    join m_a_rcved_flow b on a.id=b.rcvbl_amt_id

    where a.org_no like concat({组织机构（必填）},'%')

      and if((ifnull({截止账期},'')=''),(1=1),(a.rcvbl_ym<={截止账期}))

      and a.release_date<=date_format({截止日期（必填）},'%Y%m%d')

      and b.rcved_date>date_format({截止日期（必填）},'%Y-%m-%d')

    group by a.id

  ) t on a.id=t.id

  where a.org_no like concat({组织机构（必填）},'%')

    and if((ifnull({截止账期},'')=''),(1=1),(a.rcvbl_ym<={截止账期}))

    and a.release_date<=date_format({截止日期（必填）},'%Y%m%d')

    and a.rcvbl_amt-(a.rcved_amt-ifnull(t.this_rcved_amt,0))>0

  union all

  select a.id,a.org_no,a.cons_no,a.rcvbl_ym,a.release_date

    ,a.rcvbl_amt,a.rcved_amt-ifnull(t.this_rcved_amt,0) rcved_amt

    ,a.rcvbl_amt-(a.rcved_amt-ifnull(t.this_rcved_amt,0)) qf

  from m_a_rcvbl_flow_arc a

  join (

    select a.id,sum(this_rcved_amt) this_rcved_amt

    from m_a_rcvbl_flow_arc a

    join m_a_rcved_flow b on a.id=b.rcvbl_amt_id

    where a.org_no like concat({组织机构（必填）},'%')

      and if((ifnull({截止账期},'')=''),(1=1),(a.rcvbl_ym<={截止账期}))

      and a.release_date<=date_format({截止日期（必填）},'%Y%m%d')

      and b.rcved_date>date_format({截止日期（必填）},'%Y-%m-%d')

    group by a.id

  ) t on a.id=t.id

  where a.org_no like concat({组织机构（必填）},'%')

    and if((ifnull({截止账期},'')=''),(1=1),(a.rcvbl_ym<={截止账期}))

    and a.release_date<=date_format({截止日期（必填）},'%Y%m%d')

    and a.rcvbl_amt-(a.rcved_amt-ifnull(t.this_rcved_amt,0))>0

) ta

left join m_c_cons a on a.cons_no=ta.cons_no

left join ac_org o on ifnull(a.org_no,ta.org_no)=o.id

left join ac_org x on left(o.id,7)=x.id

order by x.`name`,o.`name`,ta.cons_no,ta.rcvbl_ym

-- 文件名：1.5倍用户查询
select x.short_name 公司名称,cons.org_no 单位编码,o.`name` 单位名称

	,cons.cons_no 用户编号,replace(replace(cons.cons_name,'\n',''),'\t',' ') 用户名称

	,mp.mp_no 计量点,consprc.prc_code 电价码

  ,left(consprc.create_time,10) 用户电价创建时间,left(consprc.update_time,10) 用户电价更新时间

from m_c_cons cons

join ac_org o on cons.org_no=o.id

join ac_org x on left(o.id,7)=x.id

join m_c_sp sp on cons.id=sp.cons_id

join m_c_mp mp on sp.id=mp.sp_id

join m_c_cons_prc consprc on mp.tariff_id=consprc.id and consprc.prc_code in('40002011501','40001051500','40001021500','40002021500','40002021500','40001031500','40002011500','40002031500','40001041500','40001021500','40002021500','40001021500','40002011500','40002021501','40001031502','40001031500','40001031500','40001021502')

where cons.org_no like concat({组织},'%')

-- 文件名：数电发票查询
select o.`name` '管理单位',r.id '抄表段编号',r.`name` '抄表段名称',c.cons_no '户号',c.cons_name '户名',c.elec_addr '用电地址',c.rural_cons_code '城农网标志',

c.note_type_code '票据类型',rf.rcvbl_ym '账期',t.t_settle_pq '电量',t.t_amt '电费',t.prc_code '电价码', t.cat_prc_name '电价名称',

t.last_mr_num '起度',t.this_read '止度',t.t_factor '综合倍率',cf.this_cont_pq '是否有优惠电量',rf.settle_flag '用户电费结清标志',

ip.type_code '票据打印类型',ip.print_amt '票据打印金额',ip.print_num '票据打印次数',ip.print_date '票据打印时间'

from (

select d.mp_id ,pa.calc_id,pa.prc_snap_id,prc.prc_code,prc.cat_prc_name,pa.t_settle_pq t_settle_pq,pa.t_amt t_amt,

d.last_mr_num,d.this_read,d.t_factor,d.cons_no

from  (select calc_id,prc_snap_id,para_vn,prc_code,ym,sum(t_settle_pq) t_settle_pq,sum(t_amt) t_amt from m_e_cons_prc_amt_arc where org_no like CONCAT({组织},'%') and ym>={电费年月起} and  ym<={电费年月止} group by calc_id, ym ) pa

left join m_e_consprc_snap_arc cs on cs.id = pa.prc_snap_id

left join m_e_mp_para_snap_arc mps on mps.calc_id = cs.calc_id

inner join ( select mp_id,cons_no,last_mr_num,this_read,t_factor from m_r_data_arc where org_no  like concat({组织}, '%') and read_type_code='11'  and

 amt_ym>='{电费年月起}'  and amt_ym<='{电费年月止}' group by mp_id, amt_ym) d  on d.mp_id = mps.mp_id

left join m_e_cat_prc prc on prc.id = pa.para_vn = prc.para_vn and pa.prc_code = prc.prc_code

where  if(({组织} is null or {组织}=''),(1=1), cs.org_no like concat({组织}, '%') and  mps.org_no  like concat({组织}, '%')) ) t

left join m_e_cont_fee_arc cf on t.calc_id = cf.calc_id  and cf.org_no like concat({组织}, '%')

inner join m_a_rcvbl_flow_arc rf on t.calc_id = rf.calc_id  and rf.org_no like concat({组织}, '%')

left join m_a_inv_print_flow ip on rf.id = ip.rcvbl_amt_id  and ip.org_no like concat({组织}, '%')

left join m_e_cons_snap_arc sc on  sc.id = t.prc_snap_id  and sc.org_no like concat({组织}, '%')

left join m_c_cons c on c.cons_no = t.cons_no  and c.org_no like concat({组织}, '%')

left join m_r_sect r on c.mr_sect_no = r.id  and r.org_no like concat({组织}, '%')

left join ac_org o on o.`code` = c.org_no

where if(({户名} is null or {户名}=''),(1=1),c.cons_name like CONCAT('%',{户名},'%'))

and if(({户号} is null or {户号}=''),(1=1),c.cons_no like CONCAT('%',{户号},'%'))

and if(({抄表段编号} is null or {抄表段编号}=''),(1=1),c.mr_sect_no like CONCAT({抄表段编号},'%'))

and if(({抄表段名称} is null or {抄表段名称}=''),(1=1),r.`name` like CONCAT({抄表段名称},'%'))



union



select o.`name` '管理单位',r.id '抄表段编号',r.`name` '抄表段名称',c.cons_no '户号',c.cons_name '户名',c.elec_addr '用电地址',c.rural_cons_code '城农网标志',

c.note_type_code '票据类型',rf.rcvbl_ym '账期',t.t_settle_pq '电量',t.t_amt '电费',t.prc_code '电价码', t.cat_prc_name '电价名称',

t.last_mr_num '起度',t.this_read '止度',t.t_factor '综合倍率',cf.this_cont_pq '是否有优惠电量',rf.settle_flag '用户电费结清标志',

ip.type_code '票据打印类型',ip.print_amt '票据打印金额',ip.print_num '票据打印次数',ip.print_date '票据打印时间'

from (

select d.mp_id ,pa.calc_id,pa.prc_snap_id,prc.prc_code,prc.cat_prc_name,pa.t_settle_pq t_settle_pq,pa.t_amt t_amt,

d.last_mr_num,d.this_read,d.t_factor,d.cons_no

from  (select calc_id,prc_snap_id,para_vn,prc_code,ym,sum(t_settle_pq) t_settle_pq,sum(t_amt) t_amt from m_e_cons_prc_amt_arc where org_no like CONCAT({组织},'%') and ym>={电费年月起} and  ym<={电费年月止} group by calc_id, ym ) pa

left join m_e_consprc_snap_arc cs on cs.id = pa.prc_snap_id

left join m_e_mp_para_snap_arc mps on mps.calc_id = cs.calc_id

inner join ( select mp_id,cons_no,last_mr_num,this_read,t_factor from m_r_data_arc where org_no  like concat({组织}, '%') and read_type_code='11'  and

 amt_ym>='{电费年月起}'  and amt_ym<='{电费年月止}' group by mp_id, amt_ym) d  on d.mp_id = mps.mp_id

left join m_e_cat_prc prc on prc.id = pa.para_vn = prc.para_vn and pa.prc_code = prc.prc_code

where  if(({组织} is null or {组织}=''),(1=1), cs.org_no like concat({组织}, '%') and  mps.org_no  like concat({组织}, '%')) ) t

left join m_e_cont_fee_arc cf on t.calc_id = cf.calc_id  and cf.org_no like concat({组织}, '%')

inner join m_a_rcvbl_flow rf on t.calc_id = rf.calc_id  and rf.org_no like concat({组织}, '%')

left join m_a_inv_print_flow ip on rf.id = ip.rcvbl_amt_id  and ip.org_no like concat({组织}, '%')

left join m_e_cons_snap_arc sc on  sc.id = t.prc_snap_id  and sc.org_no like concat({组织}, '%')

left join m_c_cons c on c.cons_no = t.cons_no  and c.org_no like concat({组织}, '%')

left join m_r_sect r on c.mr_sect_no = r.id  and r.org_no like concat({组织}, '%')

left join ac_org o on o.`code` = c.org_no

where if(({户名} is null or {户名}=''),(1=1),c.cons_name like CONCAT('%',{户名},'%'))

and if(({户号} is null or {户号}=''),(1=1),c.cons_no like CONCAT('%',{户号},'%'))

and if(({抄表段编号} is null or {抄表段编号}=''),(1=1),c.mr_sect_no like CONCAT({抄表段编号},'%'))

and if(({抄表段名称} is null or {抄表段名称}=''),(1=1),r.`name` like CONCAT({抄表段名称},'%'))

-- 文件名：档案-电价
SELECT

  o1.name AS 供电单位,

	cons_no 用户编号,

	cons_name 用户名称,

	elec_addr 用电地址,

  p4.NAME AS 用户分类,

	p3.NAME AS 供电电压,

	p2.NAME AS 用户状态,

	(select CONCAT_WS( '-', id, name )from m_r_sect ff where id=c.mr_sect_no and ff.effect_flag=1) 抄表段编号及名称,

	p1.NAME AS 用电类别,

	(

	SELECT

		CONCAT_WS( '-', cat.prc_code, cat.cat_prc_abbr )

	FROM

		m_c_cons_prc prc,

		m_e_cat_prc cat

	WHERE

		prc.prc_code = cat.prc_code

		AND cat.para_vn = '40500000021'

		AND prc.id = (

		SELECT

			tariff_id

		FROM

			m_c_mp mp

		WHERE

			mp.cons_id = c.id

			-- AND mp.status_code IN ( '01', '02' ,'03')

			AND mp.mp_level = 1

			LIMIT 1

		)

	) 电价码及名称,

	date_format( c.build_date, '%Y-%m-%d' ) 立户时间,

	(

	SELECT NAME

	FROM

		m_p_code

	WHERE

		code_type = 'mrModeCode'

	AND

	VALUE

		= (

		SELECT

			mr.mr_mode_code

		FROM

			m_r_sect r,

			m_r_plan_day mr

		WHERE

			r.id = mr.mr_sect_no

			AND mr.effect_flag = '1'

			AND r.id = c.mr_sect_no

			LIMIT 1

		)

	) 抄表段抄表方式

FROM

	m_c_cons c


LEFT JOIN ac_org o1 ON code=c.org_no
LEFT JOIN m_p_code p4 ON code_type = 'custSortCode' AND VALUE = c.cons_sort_code AND take_effect_flag = 1
LEFT JOIN m_p_code p3 ON code_type = 'psVoltCode' AND VALUE = c.volt_code AND take_effect_flag = 1
LEFT JOIN m_p_code p2 ON code_type = 'statusCode' AND VALUE = c.status_code AND take_effect_flag = 1
LEFT JOIN m_p_code p1 ON code_type = 'elecTypeCode' AND VALUE = c.elec_type_code AND take_effect_flag = 1
WHERE

 	org_no = {供电单位}

-- 文件名：未挂采集的用户信息
select distinct o.name 单位,line_no 线路编号,line_name 线路名称,tg_no 台区编号,tg_name 台区名称,cp_no 台区关联采集点编号,cp.name 台区关联采集点名称,cons_no 户号,cons_name 户名,b.mp_no 计量点编号,c.made_no 表号

from m_c_cons a

join ac_org o on a.org_no=o.id

join m_c_mp b on a.id=b.cons_id and b.type_code='01' and b.status_code in ('01','02')

join m_c_meter c on b.id=c.mp_id

left join m_g_tg tg on b.tg_id=tg.id

left join m_g_line_tg_rela lt on tg.id=lt.tg_id and lt.rela_flag=1

left join m_g_line l on lt.line_id=l.id

left join m_r_cp cp on tg.id=cp.tg_id

where  not exists (select 1 from m_r_coll_obj f join m_r_tmnl_run g on f.cp_no=g.cp_no and f.collector_id=g.id where f.cons_id=a.id and b.id=f.mp_id and c.id=f.meter_id)

and if(ifnull({组织},'')='',(1=1),a.org_no like concat({组织}, '%')) and a.status_code in ('0','1','2','3')

order by 1,2,4,8

-- 文件名：用户发行电费明细查询
select a.org_no 单位编码,o.`name` 单位名称,a.cons_no 户号,a.cons_name 户名

 ,p4.`name` 费控类型,p2.`name` `用电类别`,p3.name 电压等级,b.prc_code 电价编码,c.cat_prc_name 电价名称

 ,sum(b.t_settle_pq) 电量,sum(t_amt) 电费

from m_e_cons_snap_arc a

join m_e_cons_prc_amt_arc b on a.id=b.calc_id

join ac_org o on a.org_no=o.id

left join m_e_cat_prc c on b.para_vn=c.para_vn and b.prc_code=c.prc_code

left join m_p_code p1 on p1.code_type='tradeCode' and p1.`value`=a.trade_type_code

left join m_p_code p2 on p2.code_type='elecTypeCode' and p2.`value`=b.elec_type_code

left join m_p_code p3 on p3.code_type='psVoltCode' and p3.`value`=a.volt_code

left join m_p_code p4 on p4.code_type='ctlMode' and p4.`value`=a.ctl_mode

where a.org_no like concat({组织},'%')

 and a.ym={年月}

group by a.cons_no,b.prc_code,a.ctl_mode

-- 文件名：用户发行电量电费_账期
select distinct

	o.name 单位,sect.id 抄表段编号,sect.name 抄表段名称,cons.cons_no 户号,cons.cons_name 户名,p1.name 用户状态

	,ym 帐期,prc_code 电价编号,cat_prc_name 电价名称,电量,电费

	,(case when zt.app_no is not null then zt.app_no else '' end) 在途抄表工单

	from m_c_cons cons

	join ac_org o on cons.org_no=o.id and o.id like concat({供电单位}, '%')

	left join m_r_sect sect on cons.mr_sect_no=sect.id

	left join (

		select cons_id,cons_no,econs.ym,eprc.prc_code,cat_prc_name,sum(t_settle_pq) 电量,sum(t_amt) 电费

			from m_e_cons_snap_arc econs

			join m_e_cons_prc_amt_arc prcamt on econs.id=prcamt.calc_id

			join m_e_cat_prc eprc on prcamt.prc_code=eprc.prc_code and prcamt.para_vn=eprc.para_vn

			where prcamt.ym={电费年月}  and prcamt.org_no like concat({供电单位}, '%')

			group by cons_id,cons_no,econs.ym,eprc.prc_code,cat_prc_name

	) df on cons.id=df.cons_id and cons.cons_no=df.cons_no

	left join (select distinct rd.app_no,cons_no from m_r_data rd join m_r_plan rp on rd.app_no=rp.app_no and rp.plan_status not in ('10','99') where rd.org_no like concat({供电单位}, '%') and rd.amt_ym={电费年月}  ) zt on cons.cons_no=zt.cons_no

  left join m_p_code p1 on p1.code_type='statusCode' and p1.value=cons.status_code

	where cons.status_code<>'9' and exists (select 1 from m_c_mp mp where mp.type_code='01' and mp.status_code in ('01','02') and mp.cons_id=cons.id)

order by 1,2,4

-- 文件名：市场化应执行1.5倍电价用户
select org1.name 县公司,org2.name 供电所,a.user_id 主体id,a.cons_no 用户编号,a.cons_name 用户名称,pcode.name 用电类别,DATE_FORMAT(max(log.unbind_time),'%Y-%m-%d') 退市时间 from m_c_market_actual_variety a join m_c_cons cons on cons.cons_no = a.cons_no left join (select value,name from m_p_code where code_type = 'elecTypeCode') pcode on pcode.value = cons.elec_type_code  left join m_c_market_user_unbind_log log on log.cons_no = a.cons_no left join ac_org org1 on org1.id = left(cons.org_no,7) left join ac_org org2 on org2.id = cons.org_no where year = 2025 and a.cons_no not in(select distinct cons_no from (select distinct user_id from m_c_market_actual_variety where year = left({电费年月},4) and month=right({电费年月},2)+0) mav join m_c_market_userinfo mcu on mav.user_id = mcu.market_user_no join m_c_mp_info mcmi on mcmi.market_user_id = mcu.id join m_c_cons mcc on mcc.id = mcmi.cons_id  where ifnull( mcmi.chg_desc, '' )!= '04') and cons.status_code!=9 and cons.org_no like concat({组织},'%') GROUP BY 1,2,3,4,5,6 order by 1,2,3,4

-- 文件名：市场化交易品种初版
SELECT o1.name AS 单位,

b.cons_no 户号,b.cons_name 户名,a.cons_name 交易品种传递户名,a.seller_name 售电公司名称,

a.tr_type_name 实际交易品种

FROM m_c_market_actual_variety_init a , m_c_cons b


LEFT JOIN ac_org o1 ON id = b.org_no
WHERE b.org_no like concat({组织},'%') and a.`year` = left({电费年月},4) and a.`month` = right({电费年月},2)

AND a.cons_no = b.cons_no  order by b.org_no,b.cons_no

-- 文件名：用户参与市场化交易情况
SELECT org1.NAME AS 县公司,org2.NAME AS 供电所,mcc.cons_no AS 用户编号,mcc.cons_name AS 用户名称,IF(mcc.status_code != 9, '正常', '销户') AS 用户状态,s.id AS 抄表段编号,s.name AS 抄表段名称,p.NAME AS 抄表段属性,IF(MAX(IF(mcmi.register_date < STR_TO_DATE({电费年月}, '%Y%m') AND IFNULL(mcmi.chg_desc, '') != '04', 1, 0)) = 1, '参与', '不参与') AS 当月是否参与交易 FROM (SELECT DISTINCT user_id FROM m_c_market_actual_variety WHERE YEAR = LEFT({电费年月},4) AND MONTH = RIGHT({电费年月},2)+0) mav JOIN m_c_market_userinfo mcu ON mav.user_id = mcu.market_user_no JOIN m_c_mp_info mcmi ON mcmi.market_user_id = mcu.id JOIN m_c_cons mcc ON mcc.id = mcmi.cons_id LEFT JOIN m_r_sect s ON s.id = mcc.mr_sect_no LEFT JOIN ac_org org1 ON org1.id = LEFT(mcc.org_no, 7) LEFT JOIN ac_org org2 ON org2.id = mcc.org_no LEFT JOIN m_p_code p ON p.code_type = 'mrSectAttr' AND p.value = s.attr WHERE mcc.org_no LIKE CONCAT({组织}, '%') GROUP BY mcc.id,org1.NAME,org2.NAME,mcc.cons_no,mcc.cons_name,mcc.status_code,s.id,s.name,s.attr ORDER BY 9 desc,1, 2

-- 文件名：一户多人口阶梯电量查询
SELECT o1.name         AS '单位',

       a.cons_no                                                     AS '户号',

       a.cons_name                                                   AS '户名',

       a.elec_addr                                                   AS '用电地址',

       a.ym                                                          AS '电费年月',

       mu.effect_population                                          AS '有效人口',

       (SELECT CONCAT('0-', GROUP_CONCAT(

               CASE

                   WHEN s.range_type_code = '33-12' THEN ''

                   ELSE (s.end_value + IFNULL(mu.level_raise_pq, 0))

                   END

               ORDER BY s.range_type_code

               SEPARATOR '-'

           ))

        FROM m_e_cat_prc cat

                 JOIN m_e_prc_scope s ON s.cat_prc_id = cat.id

        WHERE s.range_remark LIKE CONCAT('%', SUBSTR(a.ym, 6, 1), '%')

          and s.range_type_code like '%-12'

          AND cat.prc_code = b.prc_code

          AND cat.para_vn = b.para_vn)                               AS '阶梯区间',

       SUM(b.t_settle_pq - b.level_inc_pq)                           AS '1档电量',

       SUM(IF(b.level_num = 1, b.t_amt, 0))                          AS '1档电费',

       SUM(CASE WHEN b.level_num = 2 THEN b.level_inc_pq ELSE 0 END) AS '2档电量',

       SUM(CASE WHEN b.level_num = 2 THEN b.t_amt ELSE 0 END)        AS '2档电费',

       SUM(CASE WHEN b.level_num = 3 THEN b.level_inc_pq ELSE 0 END) AS '3档电量',

       SUM(CASE WHEN b.level_num = 3 THEN b.t_amt ELSE 0 END)        AS '3档电费',

       SUM(IFNULL(b.t_amt, 0))                                       AS '总电费'

FROM m_e_cons_snap_arc a

         JOIN m_e_cons_prc_amt_arc b ON a.id = b.calc_id

         JOIN m_a_multi_person mu ON mu.cons_no = a.cons_no

    AND a.ym BETWEEN mu.begin_month AND mu.end_month


LEFT JOIN ac_org o1 ON o1.code = a.org_no
WHERE 1=1

  and if(({组织} is null or {组织}=''),(1=1),a.org_no LIKE concat({组织},'%'))

  AND if(({电费年月} is null or {电费年月}=''),(1=1),a.ym = {电费年月})

  AND b.elec_type_code LIKE '2%'

  and if(({户号} is null or {户号}=''),(1=1),(a.cons_no={户号}))

GROUP BY a.cons_no, b.para_vn, b.prc_code, a.id

-- 文件名：当月用户未抄表及发行零电量信息
select * from (select distinct

	o.name 单位,sect.id 抄表段编号,sect.name 抄表段名称,cons.cons_no 户号,cons.cons_name 户名,p2.name 用户状态,cons.elec_addr 用电地址,rcvbl_ym 账期,dl 发行电量

	from m_c_cons cons

	join ac_org o on cons.org_no=o.id and o.id like concat(ifnull({组织},''),'%')

	left join m_r_sect sect on cons.mr_sect_no=sect.id

	left join (select cons_no,rcvbl_ym,sum(t_pq) dl

      from ( select cons_no,rcvbl_ym,t_pq from m_a_rcvbl_flow where org_no like concat(ifnull({组织},''),'%')  and rcvbl_ym={电费年月} and id not in (select id from m_a_rcvbl_flow_arc where org_no like concat(ifnull({组织},''),'%')  and rcvbl_ym={电费年月})

            union all

            select cons_no,rcvbl_ym,t_pq from m_a_rcvbl_flow_arc where org_no like concat(ifnull({组织},''),'%')  and rcvbl_ym={电费年月}

      ) x group by cons_no,rcvbl_ym

  ) rcvbl on cons.cons_no=rcvbl.cons_no

	left join m_p_code p2 on p2.code_type='statusCode' and p2.value=cons.status_code

	where cons.status_code<>'9' and exists (select 1 from m_c_mp mp where mp.type_code='01' and mp.status_code in ('01','02') and mp.cons_id=cons.id)

	) x where ifnull(发行电量,0)=0

order by 1,2,4

-- 文件名：昭觉欠费查询
select distinct o.name 管理单位,a.cons_no 用户编号,cons.cons_name 用户名称,a.rcvbl_ym 应收年月,a.rcvbl_amt 应收金额,a.rcved_amt 实收金额

,a.rcvbl_penalty 应收违约金额,a.rcved_penalty 实收违约金额,(a.rcvbl_amt+a.rcvbl_penalty-a.rcved_amt-a.rcved_penalty) 总欠费金额

,a.t_pq 总电量,p1.name 电费类别,b.name 抄表段名称,b.id 抄表段编号,e.mobile 联系电话,p2.name 欠费类型,u1.user_name 抄表员,u2.user_name 走收催费员

from m_c_cons cons

join ac_org o on cons.org_no=o.id and o.id like '5100109%'

join m_a_rcvbl_flow a on a.cons_no=cons.cons_no

left join m_r_sect b on a.mr_sect_no=b.id

left join m_r_oper_activity c1 on b.id=c1.mr_sect_no and c1.act_code='03'

left join m_r_oper_activity c2 on b.id=c2.mr_sect_no and c2.act_code='21'

left join ac_user u1 on u1.id=c1.operator_no

left join ac_user u2 on u2.id=c2.operator_no

left join m_c_cons_contact_rela d on cons.id=d.cons_id

left join m_c_contact e on d.contact_id=e.id

left join m_p_code p1 on p1.code_type='paTypeCode' and p1.value=a.amt_type

left join m_p_code p2 on p2.code_type='ctlMode' and p2.value=a.ctl_mode

where a.settle_flag<>'03'

order by 管理单位,用户编号,应收年月

-- 文件名：关口表信息查询
select

 o1.name AS 单位名称,

 mp.mp_no 计量点编号,

 mp.mp_name 计量名称,

 p2.name AS 计量点分类,

 (case mp.status_code when '01' then '设立' when '02' then '在用' when '03' then '停用' when '04' then '撤销' else '其他' end) 计量点状态,

 line.line_name 线路,

 tq.tg_name 台区,

 rs1.CONCAT_WS( '|', id, NAME ) AS 抄表段,

 me.made_no 出厂编号,

 me.t_factor 综合倍率,

 m_read.mr_read 示数,

 date_format(m_read.mr_date,'%Y-%m-%d') 最后抄表日期,

 ch.chkunit_name 考核单元名称,

 p1.name AS 考核单元分类,

 (case iomp.io_id when '1' then '入口计量' when '0' then '出口计量' end) 计量点标志

from m_c_mp mp

left join m_c_meter me on mp.id=me.mp_id

left join m_c_meter_read m_read on me.id=m_read.meter_id and m_read.read_type_code='11'

left join m_g_tg tq on tq.id=mp.tg_id

left join m_g_line line on line.id=mp.line_id

left join m_g_io_mp iomp on mp.id=iomp.mp_id

left join m_g_chkunit ch on iomp.chkunit_id=ch.id


LEFT JOIN ac_org o1 ON id=mp.org_no
LEFT JOIN m_p_code p2 ON p2.code_type='mpSortCode' and p2.value=mp.type_code AND take_effect_flag = 1
LEFT JOIN m_r_sect rs1 ON rs1.id = mp.mr_sect_no
LEFT JOIN m_p_code p1 ON p1.code_type='chkunitSort' and p1.value=ch.chkunit_type_code AND take_effect_flag = 1
where mp.org_no LIKE concat({组织}, '%') and mp.type_code in ('02','03','04','05')

 and if(({抄表段编号} is null or {抄表段编号}=''),(1=1),(mp.mr_sect_no={抄表段编号}))

 and if(({台区名称} is null or {台区名称}=''),(1=1),(tq.tg_name LIKE concat('%',{台区名称}, '%')))

 and if(({线路名称} is null or {线路名称}=''),(1=1),(line.line_name LIKE concat('%',{线路名称},'%')))

 and if(({计量点状态} is null or {计量点状态}=''),(1=1),(mp.status_code={计量点状态}))

 and if(({计量点编号} is null or {计量点编号}=''),(1=1),(mp.mp_no={计量点编号}))

 and if(({计量点分类} is null or {计量点分类}=''),(1=1),(mp.type_code={计量点分类}))

and if(({出厂编号} is null or {出厂编号}=''),(1=1),(me.made_no LIKE concat('%',{出厂编号}, '%')))

 ORDER BY mp.org_no,line.line_name,tq.tg_name,mp.id,mp.status_code

-- 文件名：农维费用户明细查询
SELECT

org_name 单位,tg_no 台区编号,tg_name 台区名称, cons_no 用户编号,cons_name 用户名称,elec_addr 用电地址,t_settle_pq 总电量,

t_amt 总电费,nwf_amt 农维费,nwf_prc 农维费单价,

ym 电费年月,prc_code 电价,prc_name 电价名称,p1.name AS 票据类型

FROM

m_rt_nwf_cons_amt_detail


LEFT JOIN m_p_code p1 ON code_type ="noteTypeCode" AND VALUE = note_type_code AND take_effect_flag = 1
WHERE

org_no = {单位} and   ym = {电费年月}

-- 文件名：分布式电源客户资料
select a.org_no 单位编号,o.`name` 管理单位,a.gc_no 发电用户编号,a.gc_name 发电用户名称,p1.`name` 发电用户状态

  ,concat(date_format(a.gc_date,'%Y-%m-%d'),'') 首次并网日期

  ,p7.`name` 发电量消纳方式,p8.`name` 业主分类

	,y.pro_no 项目编号,y.pro_app_doc 项目批复文号,a.gc_addr 发电地址

  ,ln.line_no 线路编码,ln.line_name 线路名称,tg.tg_no 台区编号,tg.tg_name 台区名称,tg.tg_cap 台区容量,a.mr_sect_no 抄表段编码,rs.`name` 抄表段名称

  ,a.contract_cap 合同容量,p2.`name` 发电用户类型,p3.`name` 客户类别,p4.`name` 发电方式,p5.`name` 并网电压,p6.`name` 行业分类

  ,mp.mp_no 上网关口计量点,cm.made_no 上网关口表号,cons.cons_no 共用用户编号,cons_name 共用用户名称

from m_c_fc_gc a

join ac_org o on a.org_no=o.id

left join m_c_fc_proinfo_gc_rela x on x.gc_id=a.id

left join m_c_fc_proinfo y on x.proinfo_id=y.id

left join m_r_sect rs on a.mr_sect_no=rs.id

left join m_c_fc_gn b on a.id=b.gc_id

left join m_c_fc_gn_mp_rela gmr on b.id=gmr.gn_id

left join m_c_mp mp on gmr.mp_id=mp.id

left join m_c_meter_mp_rela mmr on mp.id=mmr.mp_id

left join m_c_meter cm on mmr.meter_id=cm.id

left join m_c_cons cons on cm.cons_id=cons.id

left join m_g_line ln on b.line_id=ln.id

left join m_g_tg tg on b.tg_id=tg.id

left join m_p_code p1 on p1.code_type='gcStatusCode' and p1.`value`=a.status_code

left join m_p_code p2 on p2.code_type='gcSortCodeType' and p2.`value`=a.gc_sort_code

left join m_p_code p3 on p3.code_type='gcType' and p3.`value`=a.gc_type

left join m_p_code p4 on p4.code_type='gcTypeCode' and p4.`value`=a.elec_gener_type

left join m_p_code p5 on p5.code_type='psVoltCode' and p5.`value`=a.volt_code

left join m_p_code p6 on p6.code_type='tradeCode' and p6.`value`=a.trade_code

left join m_p_code p7 on p7.code_type='absoMode' and p7.`value`=a.abso_mode

left join m_p_code p8 on p8.code_type='ownerClassify' and p8.`value`=a.owner_classify

where a.org_no like concat({管理单位},'%')

  and a.fc_cust_type='2'

  and if(({发电用户编号} is null or {发电用户编号}=''),(1=1),a.gc_no={发电用户编号})

  and if(({首次并网日期} is null or {首次并网日期}=''),(1=1),a.gc_date={首次并网日期})

order by a.org_no,a.gc_no

-- 文件名：抄表方式查询
select

	o1.name AS 单位名称,

	a.cons_no 用户编号,

	a.cons_name 用户名称,

	p1.`name` 用户分类,

	a.elec_addr 用电地址,

	b.mp_id 计量点编号,

	p2.`name` 计量点分类,

	b.made_no 出厂编号,

	date_format(b.this_ymd,'%Y-%m-%d') 抄表日期,

	p3.name AS 示数类型,

	b.last_mr_num 上次示数,

	b.this_read 本次示数,

	b.t_factor 综合倍率,

	b.last_mr_pq 上次抄见电量,

	b.this_read_pq 本次抄见电量,

	p2.name AS 抄表方式,

	p1.name AS 抄表状态,

	tq.tg_name 台区名称,

	line.line_name 线路名称,

	a.mr_sect_no 抄表段编号,

	rs1.name AS 抄表段名称

from m_e_cons_snap_arc a

join m_r_data_arc b on a.id=b.calc_id

left join m_c_mp c on c.id=b.mp_id

left join m_g_tg tq on tq.id=c.tg_id

left join m_g_line line on line.id=c.line_id

left join m_p_code p1 on p1.code_type='custSortCode' and p1.`value`=a.cons_sort_code

left join m_p_code p2 on p2.code_type='mpSortCode' and p2.`value`=c.type_code


LEFT JOIN ac_org o1 ON id=a.org_no
LEFT JOIN m_p_code p3 ON p3.code_type ='readTypeCode' and p3.value=b.read_type_code AND take_effect_flag = 1
LEFT JOIN m_p_code p2 ON p2.code_type='mrModeCode' and p2.value=b.actual_mode AND take_effect_flag = 1
LEFT JOIN m_p_code p1 ON p1.code_type='mrStatusCode' and value=b.mr_status_code AND take_effect_flag = 1
LEFT JOIN m_r_sect rs1 ON id=a.mr_sect_no
where a.org_no like concat({组织}, '%') and a.ym={电费年月}

	and exists (select 1 from m_r_plan_arc where app_no=a.app_code and plan_status='10')

	and b.made_no is not null

	and if(({抄表方式} is null or {抄表方式}=''),(1=1),(b.actual_mode={抄表方式}))

	and if(({抄表段编号} is null or {抄表段编号}=''),(1=1),(a.mr_sect_no={抄表段编号}))

	and if(({台区名称} is null or {台区名称}=''),(1=1),(tq.tg_name LIKE concat('%',{台区名称}, '%')))

	and if(({线路名称} is null or {线路名称}=''),(1=1),(line.line_name LIKE concat('%',{线路名称}, '%')))

	and if(({户名} is null or {户名}=''),(1=1),a.cons_name like CONCAT('%',{户名},'%'))

	and if(({户号} is null or {户号}=''),(1=1),a.cons_no like CONCAT('%',{户号},'%'))

	and if(({抄表状态} is null or {抄表状态}=''),(1=1),(b.mr_status_code={抄表状态}))

	and if(({用户分类} is null or {用户分类}=''),(1=1),(a.cons_sort_code={用户分类}))

	and if(({计量点分类} is null or {计量点分类}=''),(1=1),(c.type_code={计量点分类}))

order by a.org_no,a.cons_no,a.cons_name

-- 文件名：绿电环境价值退补查询
select  ym 电费年月,org_no 组织编码,b.name 机构名称,market_user_no	市场化主体id,market_user_name	市场化主体名称,cons_no	用户编号,social_credit_code	社会编号,pq	绿电环境价值电量,ifnull(a.update_user,prc)	电价,date_format(a.create_time,'%Y-%m-%d %H:%I:%s')	创建时间,date_format(a.update_time,'%Y-%m-%d %H:%I:%s') 更新时间

  from m_t_deal_volume a left join ac_org b on a.org_no = b.code where ym={电费年月}and deal_type = 5213 and a.org_no like CONCAT({组织机构},"%")

-- 文件名：市场化用户代理售电公司信息
select a.market_user_no 市场化客户编号,a.market_user_name 市场化客户名称,a.social_credit_code 统一社会信用代码,a.linkman 联系人,a.telephone 联系方式,a.cust_addr 客户地址,a.create_time 注册时间,a.effect_date 生效日期,a.expiry_date 失效日期,cmav1.seller_name AS 代理售电公司 from m_c_market_userinfo a where a.status = 0 and EXISTS(select 1 from m_c_mp_info mp join m_c_cons cons on mp.cons_id = cons.id where mp.market_user_id = a.id and cons.org_no like concat({组织},'%'))

LEFT JOIN m_c_market_actual_variety cmav1 ON seller_name is not null and user_id = a.market_user_no ORDER BY year desc,month desc

-- 文件名：应收统计
select o1.name AS 单位,

 ys.年月,

 ys.总应收,

 ys.总电量,

 b.售电收入,

 ys.代征总电费

 from (

SELECT

    a.org_no,

		a.ym 年月,

    sum(ifnull(c.t_amt, 0)) 总应收,

	sum(ifnull(c.t_settle_pq, 0)) 总电量,

	sum(ifnull(t_pl_amt, 0)) 代征总电费

	FROM

		m_e_Cons_Snap_Arc a

	JOIN m_c_cons acons ON a.cons_id = acons.id

	LEFT JOIN ac_org co ON a.org_no = co. CODE

	LEFT JOIN m_e_Consprc_Snap_Arc b ON a.id = b.calc_id

	LEFT JOIN m_e_Cons_Prc_Amt_Arc c ON a.id = c.calc_id


LEFT JOIN ac_org o1 ON id=ys.org_no
	WHERE b.id = c.prc_snap_id

	AND a.org_no LIKE concat({供电单位}, '%')

	AND b.org_no LIKE concat({供电单位}, '%')

	AND c.org_no LIKE concat({供电单位}, '%')

	AND ifnull(c.Elec_Type_Code, 0) <> '000' --  排除零电价

	AND IFNULL(b.Data_Src, '01') NOT IN ('98', '99')

	AND (c.t_settle_pq <> 0 OR c.t_amt <> 0)

	AND a.ym={电费年月}

	GROUP BY a.org_no

) ys

left join

(

	SELECT

		org_no,

		SUM(ifnull(this_rcved_amt,0)) 售电收入

	FROM

		m_a_rcved_flow

	WHERE org_no LIKE concat({供电单位}, '%')

	AND rcvbl_ym ={电费年月}

	GROUP BY org_no

) b on b.org_no=ys.org_no

UNION

select

'合计' 单位,

 {电费年月} 年月,

 SUM(ifnull(ys.总应收,0)) 总应收,

 SUM(ifnull(ys.总电量,0)) 总电量,

 SUM(ifnull(b.售电收入,0)) 售电收入,

 SUM(ifnull(ys.代征总电费,0)) 代征总电费

 from (

SELECT

    a.org_no,

		a.ym 年月,

    sum(ifnull(c.t_amt, 0)) 总应收,

	sum(ifnull(c.t_settle_pq, 0)) 总电量,

	sum(ifnull(t_pl_amt, 0)) 代征总电费

	FROM

		m_e_Cons_Snap_Arc a

	JOIN m_c_cons acons ON a.cons_id = acons.id

	LEFT JOIN ac_org co ON a.org_no = co. CODE

	LEFT JOIN m_e_Consprc_Snap_Arc b ON a.id = b.calc_id

	LEFT JOIN m_e_Cons_Prc_Amt_Arc c ON a.id = c.calc_id

	WHERE b.id = c.prc_snap_id

	AND a.org_no LIKE concat({供电单位}, '%')

	AND b.org_no LIKE concat({供电单位}, '%')

	AND c.org_no LIKE concat({供电单位}, '%')

	AND ifnull(c.Elec_Type_Code, 0) <> '000' --  排除零电价

	AND IFNULL(b.Data_Src, '01') NOT IN ('98', '99')

	AND (c.t_settle_pq <> 0 OR c.t_amt <> 0)

	AND a.ym={电费年月}

	GROUP BY a.org_no

) ys

left join

(

	SELECT

		org_no,

		SUM(ifnull(this_rcved_amt,0)) 售电收入

	FROM

		m_a_rcved_flow

	WHERE org_no LIKE concat({供电单位}, '%')

	AND rcvbl_ym ={电费年月}

	GROUP BY org_no

) b on b.org_no=ys.org_no

-- 文件名：当月未抄表及零电量信息(用户和关口表)
select * from (

  select distinct

	o.name 单位,sect.id 抄表段编号,sect.name 抄表段名称,'用户' 分类,cons.cons_no 户号,cons.cons_name 户名,p2.name 用户状态,cons.elec_addr 用电地址,made_no 表号,rd.t_factor 倍率,rd.last_mr_num 起度,rd.this_read 止度,ifnull(this_read_pq,mp_ap_t_pq) 抄见电量,p1.name 抄表方式

	from m_c_cons cons

	join ac_org o on cons.org_no=o.id and o.id like concat(ifnull({组织},''),'%')

  join m_c_mp mp on mp.type_code='01' and mp.status_code in ('01','02') and mp.cons_id=cons.id

  left join m_e_mp_para_snap_arc mpsnap on mp.id=mpsnap.mp_id and mpsnap.ym={电费年月}

	left join m_r_sect sect on cons.mr_sect_no=sect.id

	left join m_r_data_arc rd on cons.cons_no=rd.cons_no and mp.id=rd.mp_id and amt_ym={电费年月}  and rd.read_type_code='11'

	left join m_p_code p1 on p1.code_type='mrModeCode' and p1.value=rd.actual_mode

	left join m_p_code p2 on p2.code_type='statusCode' and p2.value=cons.status_code

	where cons.status_code<>'9'

	union all

	select distinct

	o.name 单位,sect.id 抄表段编号,sect.name 抄表段名称,p3.name 分类,mp.mp_no 户号,mp.mp_name 户名,p2.name 用户状态,mp.mp_addr 用电地址,made_no 表号,rd.t_factor 倍率,rd.last_mr_num 起度,rd.this_read 止度,this_read_pq 抄见电量,p1.name 抄表方式

	from m_c_mp mp

	join ac_org o on mp.org_no=o.id and o.id like concat(ifnull({组织},''),'%')

	left join m_r_sect sect on mp.mr_sect_no=sect.id

	left join m_r_data_arc rd on mp.id=rd.mp_id and amt_ym={电费年月}  and rd.read_type_code='11'

	left join m_p_code p1 on p1.code_type='mrModeCode' and p1.value=rd.actual_mode

	left join m_p_code p2 on p2.code_type='mpStatus' and p2.value=mp.status_code

	left join m_p_code p3 on p3.code_type='mpSortCode' and p3.value=mp.type_code

	where mp.type_code<>'01' and mp.status_code in ('01','02') and mp.meter_flag='1'

	) x where ifnull(抄见电量,0)=0

	order by 1,2,4

-- 文件名：大竹往月欠费收费情况信息查询_新
select * from (

select

o.name 单位

,cons.cons_no 户号

,cons.cons_name 户名

,p1.name 当前电费状态

,ys.rcvbl_ym 电费年月

,ys.rcvbl_amt 应收总电费

,ss.rcved_amt 实收电费

,(ys.rcvbl_amt-ss.rcved_amt) 截至统计日期欠费

,concat('',ys.penalty_bgn_date) 违约金起算日期

,days 截至统计日期违约金天数

,(case when ifnull(elec_type_code,'') like '20%'

then round(days*(rcvbl_amt-rcved_amt)*0.001,2)

else round(days*(rcvbl_amt-rcved_amt)*0.002,2)

end ) 截至统计日期应收违约金

,ss.this_penalty 实收违约金

from m_c_cons cons

join ac_org o on o.id=cons.org_no

join (select

id,org_no,cons_no,rcvbl_ym,rcvbl_amt,settle_flag,penalty_bgn_date

,(case when penalty_bgn_date>=ifnull({实收日期},now())

then 0 else (to_days(ifnull({实收日期},now()))-to_days(penalty_bgn_date))

end ) days

from m_a_rcvbl_flow

where org_no like concat(ifnull({组织},''),'%')

and rcvbl_ym>=ifnull({电费年月起},DATE_FORMAT(now(),'%Y%m'))

and rcvbl_ym<=ifnull({电费年月止},DATE_FORMAT(now(),'%Y%m'))

and id not in (

select id from m_a_rcvbl_flow_arc

where org_no like concat(ifnull({组织},''),'%')

and rcvbl_ym>=ifnull({电费年月起},DATE_FORMAT(now(),'%Y%m'))

and rcvbl_ym<=ifnull({电费年月止},DATE_FORMAT(now(),'%Y%m'))

)

union all

select

id,org_no,cons_no,rcvbl_ym,rcvbl_amt,settle_flag,penalty_bgn_date

,(case when penalty_bgn_date>=ifnull({实收日期},now())

then 0 else (to_days(ifnull({实收日期},now()))-to_days(penalty_bgn_date))

end ) days

from m_a_rcvbl_flow_arc

where org_no like concat(ifnull({组织},''),'%')

and rcvbl_ym>=ifnull({电费年月起},DATE_FORMAT(now(),'%Y%m'))

and rcvbl_ym<=ifnull({电费年月止},DATE_FORMAT(now(),'%Y%m'))

) ys on cons.cons_no=ys.cons_no

left join (

select

rcvbl_amt_id

,sum(this_rcved_amt) rcved_amt

,sum(this_penalty) this_penalty

from m_a_rcved_flow a

where rcved_date<=ifnull({实收日期},now())

and org_no like concat(ifnull({组织},''),'%')

group by rcvbl_amt_id

) ss on ys.id=ss.rcvbl_amt_id

left join m_p_code p1 on p1.code_type='settleflag' and p1.value=ys.settle_flag

) x where 截至统计日期欠费>0

order by 1,2,5

-- 文件名：渠道收费统计
select o1.name AS 单位,d.name 渠道,f.name 付款方式,sum(ifnull(p.rcv_amt,0)) 金额, count(*) 笔数

from  m_a_pay_flow p

    left join m_a_pc_tran s on p.id=s.charge_id

    LEFT JOIN m_p_code f on p.settle_mode=f.value and f.code_type='settleMode'

    LEFT JOIN m_p_code d on p.pay_mode=d.value and d.code_type='payMode'

    left join m_sm_sale_outlet_device a on a.deviceCode = s.terminal_no and dataStatus='1'

    left join m_sm_sale_outlet_info b on a.saleOutletId=b.id

    left join ac_org c on b.orgId=c.id


LEFT JOIN ac_org o1 ON id=ifnull(c.code,p.dept_no)
where p.rcved_date>={开始时间} and p.rcved_date < {结束时间}  and ifnull(c.code,p.dept_no) like concat({单位},"%") and p.org_no like concat(substring({单位},1,7),"%")

group by ifnull(c.code,p.dept_no),d.name,f.name

union

select '汇总' 单位,'' 渠道,'' 付款方式,sum(ifnull(p.rcv_amt,0)) 金额, count(*) 笔数

from  m_a_pay_flow p

    left join m_a_pc_tran s on p.id=s.charge_id

    left join m_sm_sale_outlet_device a on a.deviceCode = s.terminal_no and dataStatus='1'

    left join m_sm_sale_outlet_info b on a.saleOutletId=b.id

    left join ac_org c on b.orgId=c.id

where p.rcved_date>={开始时间} and p.rcved_date < {结束时间}  and ifnull(c.code,p.dept_no) like concat({单位},"%") and p.org_no like concat(substring({单位},1,7),"%")

-- 文件名：往月欠费收费查询
select org_name 单位

,cons_no 户号

,cons_name 户名

,dfzt 当前电费状态

,rcvbl_ym 电费年月

,rcved_ym 实收年月

,rcved_date 实收日期

,rcvbl_amt 应收总电费

,this_rcved_amt 实收电费

,penalty_bgn_date 违约金计算日期

,days 截至实收日期违约金应计算天数

,(case when ifnull(elec_type_code,'') like '20%' then round(days*(rcvbl_amt-rcved_amt+this_rcved_amt)*0.001,2) else round(days*(rcvbl_amt-rcved_amt+this_rcved_amt)*0.002,2) end ) 截至实收日期应收违约金

,this_penalty 实收违约金

from (select a.org_no,org.name org_name,a.cons_no,a.cons_name,a.elec_type_code,b.settle_flag,code1.name dfzt,b.rcvbl_ym,c.rcved_ym,c.rcved_date,b.rcvbl_amt,b.rcved_amt,c.this_rcved_amt,b.penalty_bgn_date,c.this_penalty,(case when to_days(b.penalty_bgn_date)>=to_days(c.rcved_date) then 0 else (to_days(c.rcved_date)-to_days(b.penalty_bgn_date)) end ) days

from m_c_cons  a

join m_a_rcvbl_flow b on a.cons_no=b.cons_no

join m_a_rcved_flow  c on c.rcvbl_amt_id=b.id

join m_p_code code1 on code1.code_type='settleflag' and code1.value=b.settle_flag

join ac_org org on org.id=a.org_no

where 1=1

and if(({实收日期起} is null or {实收日期起}=''),(1=1),(c.rcved_date>={实收日期起}))

and if(({实收日期止} is null or {实收日期止}=''),(1=1),(c.rcved_date<={实收日期止}))

and if(({电费年月止} is null or {电费年月止}=''),(1=1),(b.rcvbl_ym<={电费年月止}))

and if(({电费年月起} is null or {电费年月起}=''),(1=1),(b.rcvbl_ym>={电费年月起}))

and if(({组织} is null or {组织}=''),(1=1),(a.org_no like concat({组织},'%')))

) x

order by 1,2,5

-- 文件名：根据费控类型查询用户
SELECT

	o.name 供电所,

	c.cons_no 用户编号,

	c.cons_name 用户名称

FROM

	m_c_cons c

LEFT JOIN ac_org o ON c.org_no = o.id

WHERE

 c.org_no LIKE concat({供电单位}, '%')

AND c.ctl_mode = {费控类型}

-- 文件名：增值税专用电子发票用户查询
select

       a.供电单位 供电所,a.用户户号 户号,a.用户户名 户名,{电费年月} 电费年月,

       dd.prc_start 起码, dd.prc_end 止码,dd.prc_bl 倍率,dd.sec_pq 抄见电量,a.总电量-dd.total_pq 加减电量,a.总电量 计费电量,aa.prc 电价,a.总电费 电费,round(a.总电费/a.总电量,3) 均价

           from (select a.id,co.name 供电单位 ,a.cons_no 用户户号,a.cons_name 用户户名,a.mr_sect_no 抄表段, a.volt_code 供电电压,b.prc_code 电价码,

        sum(ifnull(c.t_settle_pq, 0)) 总电量,sum(ifnull(c.t_amt, 0)) 总电费

FROM

	m_e_Cons_Snap_Arc a

        join m_c_cons  acons

         on a.cons_id=acons.id #and acons.note_type_code='02'

        left join ac_org co on a.org_no=co.code

        LEFT JOIN m_e_Consprc_Snap_Arc b on a.id=b.calc_id

        LEFT JOIN m_e_Cons_Prc_Amt_Arc c on a.id=c.calc_id



        where b.id=c.prc_snap_id

        -- and b.data_src !='03'

        and a.org_no like concat({组织},'%')

        and b.org_no like concat({组织},'%')

        and c.org_no like concat({组织},'%')

        and a.ym={电费年月}

        and b.ym={电费年月}

        and c.ym={电费年月}

        and ifnull(c.Elec_Type_Code, 0) <> '000' --  排除零电价

        and IFNULL(b.Data_Src, '01') not in ('98', '99')

        and (c.t_settle_pq <> 0 or c.t_amt <> 0)

        group by a.cons_no) a

left join (select calc_id,group_concat(t_factor)  prc_bl,

                        group_concat(r.last_mr_num) prc_start,

                        group_concat(r.this_read) prc_end,

                        group_concat(r.this_read_pq) sec_pq,

                        sum(r.this_read_pq) total_pq,

                        r.org_no,r.cons_no

                        from m_r_data_arc r

                        join m_c_cons  acons

         on r.cons_no=acons.cons_no #and acons.note_type_code='02'

                        where  r.org_no like concat({组织},'%')

                        and r.amt_ym={电费年月} and read_type_code='11'

     group by calc_id) dd on a.id=dd.calc_id

 join (select p1.name useele,prc.cat_prc_abbr,prc.prc_code,max(det.kwh_prc) prc,p2.name voltname

                    from m_p_code p1,

                    m_p_code p2,

                    m_e_cat_prc prc,

                    m_e_cat_prc_det det

                    where p1.code_type='elecTypeCode'

                    and p2.code_type='prcVoltCode'

                    and p1.value=prc.elec_type_code

                    and p2.value=prc.prc_volt_code

                    and det.cat_prc_id=prc.id

                    -- and p1.p_code is null

                     group by prc.prc_code)aa on aa.prc_code=a.电价码

 order by a.用户户名

-- 文件名：欠费情况查询
SELECT

	o1.name AS 单位,

	a.cons_no 户号,

        c.orgn_cons_no 原户号,

	c.cons_name 户名,

	c.elec_addr 用电地址,

	rs1.CONCAT_WS( '|', id, NAME ) AS 抄表段信息,

	(

	SELECT

		CONCAT_WS( '|', tg_no, tg_name )

	FROM

		m_g_tg

	WHERE

		id in ( SELECT tg_id FROM m_c_mp mp WHERE mp.cons_id = c.id and tg_id is not null )

	  limit 1

	) 台区,

	(

	SELECT

		IFNULL( CONCAT_WS( '|', mobile, office_tel, homephone ), '' )

	FROM

		m_c_cons_contact_rela b,

		m_c_contact d

	WHERE

		b.cons_id = c.id

		AND b.contact_id = d.id

		AND ( d.mobile IS NOT NULL OR office_tel IS NOT NULL OR homephone IS NOT NULL )  limit 1

	) 电话,

	(select user_name from ac_user where id=( SELECT f.operator_no FROM m_r_oper_activity f WHERE f.effect_flag = 1 AND f.act_code = '03'  and f.mr_sect_no=a.mr_sect_no limit 1)) 抄表员,

	a.t_pq 电量,

	a.rcvbl_amt 电费,

	( a.rcvbl_amt - a.rcved_amt ) 欠费,

	a.rcvbl_ym 电费年月,

	p2.name AS 电费类型,

	p1.name AS 电费类别

FROM

	m_c_cons c,

	m_a_rcvbl_flow a


LEFT JOIN ac_org o1 ON code =a.org_no
LEFT JOIN m_r_sect rs1 ON rs1.id = a.mr_sect_no
LEFT JOIN m_p_code p2 ON code_type='ctlMode' and value=a.ctl_mode AND take_effect_flag = 1
LEFT JOIN m_p_code p1 ON code_type='paTypeCode' and value=a.amt_type AND take_effect_flag = 1
WHERE

	a.cons_no = c.cons_no

	and a.rcvbl_amt<>0

	-- and a.ctl_mode='03'

	and a.settle_flag<>'03'

and a.org_no like CONCAT({供电单位},'%')

AND a.rcvbl_ym >= {开始电费年月}

and   a.rcvbl_ym <= {截止电费年月}

order by a.cons_no,a.rcvbl_ym

-- 文件名：疫情期间优惠电费用户查询_未发行
select a.ym 电费年月,

o2.name AS 分公司,

a.org_no 单位编码,

o1.name AS 供电所,

a.mr_sect_no 抄表段,

a.cons_no 户号,

a.cons_name 户名,

p1.name AS 行业类别,

max(b.prc_code) 电价码,

ecp1.cat_prc_name AS 电价名称,

sum(b.t_settle_pq) 营销总电量,

sum(b.t_amt) 营销总电费,

(-1)*sum(ecpa1.t_amt) 优惠电费

from m_e_cons_snap a,m_e_cons_prc_amt b,m_e_consprc_snap c,m_r_plan r


LEFT JOIN ac_org o2 ON o2.id=substring(a.org_no,1,7)
LEFT JOIN ac_org o1 ON o1.id=a.org_no
LEFT JOIN m_p_code p1 ON code_type ='tradeCode'and value= b.trade_type_code AND take_effect_flag = 1
LEFT JOIN m_e_cat_prc ecp1 ON ecp1.prc_code = b.prc_code and para_vn = '12019070101'
LEFT JOIN m_e_cons_prc_amt ecpa1 ON ecpa1.prc_code =b.prc_code and ecpa1.calc_id =b.calc_id and ecpa1.prc_snap_id = b.prc_snap_id and ecpa1.amt_type='99'
where

a.id = b.calc_id and a.app_code=b.app_code and a.org_no =b.org_no and a.ym = b.ym

and b.calc_id = c.calc_id and b.org_no =c.org_no and b.ym = c.ym

 and b.prc_snap_id  = c.id and b.prc_code=c.prc_code

 and a.app_code = r.app_no

and a.org_no =r.org_no and a.ym = r.amt_ym

and a.ym ={电费年月}

and a.mr_sect_no = if({抄表段编号} is null or {抄表段编号}='',a.mr_sect_no,{抄表段编号})

#and a.org_no like concat(if({供电单位} is null or {供电单位}='',a.org_no,{供电单位}),'%')

and a.org_no  in (

SELECT a.id FROM ac_org a WHERE a.type = 0 AND a.`code` != '1441613'  AND a.id LIKE CONCAT({供电单位},'%')

)

and c.data_src in('01','02')

and b.prc_code in(select prc_code from m_e_price_adjust_tmp t where t.remark ='prcCode' and ifnull(instr( CONCAT(',' ,adjust_remark, ','),CONCAT(',' , a.ym, ',')) ,0) > 0 )

and b.trade_type_code not in(select prc_code  from m_e_price_adjust_tmp where remark='tradeCode' and ifnull(instr( CONCAT(',' ,adjust_remark, ','),CONCAT(',' , a.ym, ',')) ,0) > 0 )

and b.t_amt <> 0

and ifnull(b.amt_type,'') <>'99'

group by b.calc_id ,b.prc_code

-- 文件名：疫情期间优惠电费用户查询_已发行
select a.ym 电费年月,

o2.name AS 分公司,

a.org_no 单位编码,

o1.name AS 供电所,

a.mr_sect_no 抄表段,

a.cons_no 户号,

a.cons_name 户名,

p1.name AS 行业类别,

max(b.prc_code) 电价码,

ecp1.cat_prc_name AS 电价名称,

sum(b.t_settle_pq) 营销总电量,

sum(b.t_amt) 营销总电费,

(-1)*sum(ecpaa1.t_amt) 优惠电费

from m_e_cons_snap_arc a,m_e_cons_prc_amt_arc b,m_e_consprc_snap_arc c,m_r_plan_arc r


LEFT JOIN ac_org o2 ON o2.id=substring(a.org_no,1,7)
LEFT JOIN ac_org o1 ON o1.id=a.org_no
LEFT JOIN m_p_code p1 ON code_type ='tradeCode'and value= b.trade_type_code AND take_effect_flag = 1
LEFT JOIN m_e_cat_prc ecp1 ON ecp1.prc_code = b.prc_code and para_vn = '12019070101'
LEFT JOIN m_e_cons_prc_amt_arc ecpaa1 ON ecpaa1.prc_code =b.prc_code and ecpaa1.calc_id =b.calc_id and ecpaa1.prc_snap_id = b.prc_snap_id and ecpaa1.amt_type='99' and ecpaa1.ym = a.ym
where

a.id = b.calc_id and a.app_code=b.app_code and a.org_no =b.org_no and a.ym = b.ym

and b.calc_id = c.calc_id and b.org_no =c.org_no and b.ym = c.ym

 and b.prc_snap_id  = c.id and b.prc_code=c.prc_code

 and a.app_code = r.app_no

and a.org_no =r.org_no and a.ym = r.amt_ym

and a.ym ={电费年月}

and a.mr_sect_no = if({抄表段编号} is null or {抄表段编号}='',a.mr_sect_no,{抄表段编号})

#and a.org_no like concat(if({供电单位} is null or {供电单位}='',a.org_no,{供电单位}),'%')

/*and a.org_no  in (

SELECT a.id FROM ac_org a WHERE a.type = 0 AND a.`code` != '1441613'  AND a.id LIKE CONCAT({供电单位},'%')

)*/

and a.org_no ={供电单位}

and c.data_src in('01','02')

and b.prc_code in(select prc_code from m_e_price_adjust_tmp t where t.remark ='prcCode' and ifnull(instr( CONCAT(',' ,adjust_remark, ','),CONCAT(',' , a.ym, ',')) ,0) > 0 )

and b.trade_type_code not in(select prc_code  from m_e_price_adjust_tmp where remark='tradeCode' and ifnull(instr( CONCAT(',' ,adjust_remark, ','),CONCAT(',' , a.ym, ',')) ,0) > 0 )

and b.t_amt <> 0

and ifnull(b.amt_type,'') <>'99'

group by b.calc_id ,b.prc_code

-- 文件名：疫情期间优惠电费_手工
select a.ym 电费年月,

o2.name AS 分公司,

a.org_no 单位编码,

o1.name AS 供电所,

a.mr_sect_no 抄表段,

max(b.prc_code) 电价码,

ecp1.cat_prc_name AS 电价名称,

sum(b.t_settle_pq) 营销总电量,

sum(b.t_amt) 营销总电费,

(-1)*sum(ecpaa1.t_amt) 优惠电费

from m_e_cons_snap_arc a,m_e_cons_prc_amt_arc b,m_e_consprc_snap_arc c,m_r_plan_arc r,m_r_plan_day d


LEFT JOIN ac_org o2 ON o2.id=substring(a.org_no,1,7)
LEFT JOIN ac_org o1 ON o1.id=a.org_no
LEFT JOIN m_e_cat_prc ecp1 ON ecp1.prc_code = b.prc_code and ecp1.para_vn = b.para_vn
LEFT JOIN m_e_cons_prc_amt_arc ecpaa1 ON ecpaa1.prc_code =b.prc_code and ecpaa1.calc_id =b.calc_id and ecpaa1.prc_snap_id = b.prc_snap_id and ecpaa1.amt_type='99' and ecpaa1.ym = a.ym
where a.id = b.calc_id and a.id = c.calc_id and c.id = b.prc_snap_id and a.app_code = r.app_no and a.mr_sect_no = r.mr_sect_no and r.mr_sect_no = d.mr_sect_no and r.event_type = d.event_type

and d.mr_mode_code ='301'

and a.ym ={电费年月}

and a.mr_sect_no = if({抄表段编号} is null or {抄表段编号}='',a.mr_sect_no,{抄表段编号})

and a.org_no like concat(if({供电单位} is null or {供电单位}='',a.org_no,{供电单位}),'%')

and c.data_src in('01','02')

and b.prc_code in(select prc_code from m_e_price_adjust_tmp t where t.remark ='prcCode' and ifnull(instr( CONCAT(',' ,adjust_remark, ','),CONCAT(',' , a.ym, ',')) ,0) > 0 )

and b.t_amt <> 0

and ifnull(b.amt_type,'') <> '99'

group by a.org_no,a.mr_sect_no,b.prc_code

-- 文件名：用户基本信息
select org.`name` 供电单位,cons.cons_no 用户编号,cons.cons_name 用户名称,cons.orgn_cons_no 用户原户号,cons.elec_addr 用电地址,

	group_concat(distinct cc.mobile) 所有电话号码,

	group_concat(distinct cert.cert_no) 所有证件号,

	p1.`name` 用户分类,p2.`name` 用电性质,p3.`name` 费控分类,p4.`name` 用户状态,p5.`name` 供电电压,

	p7.`name` 城农网标志,p8.`name` 票据类型,

	concat(sect.id,'|',sect.`name`) 抄表段编号及名称,

	group_concat(distinct concat(ecp.prc_code,'|',ecp.cat_prc_name)) 电价码及名称,

	group_concat(distinct dm.made_no) 所有表号,

	date_format(cons.build_date,'%Y-%m-%d') 立户时间,

	p6.`name` 抄表段抄表方式,

	group_concat(distinct concat(gl.line_no,'|',gl.line_name)) 线路信息,

	group_concat(distinct concat(gt.tg_no,'|',gt.tg_name)) 台区信息,

	date_format(cons.ps_date,'%Y-%m-%d') 送电日期,cons.id 用户ID

from m_c_cons cons

join ac_org org on cons.org_no=org.id

left join m_r_sect sect on cons.mr_sect_no=sect.id

left join m_r_plan_day mrpd on cons.mr_sect_no=mrpd.mr_sect_no

left join m_c_sp sp on cons.id=sp.cons_id

left join m_c_mp mp on sp.id=mp.sp_id

left join m_c_meter_mp_rela mmr on mp.id=mmr.mp_id

left join m_d_meter dm on mmr.meter_id=dm.id

left join m_g_line gl on mp.line_id=gl.id

left join m_g_tg gt on mp.tg_id=gt.id

left join m_c_cons_prc ccp on mp.tariff_id=ccp.id

left join m_e_cat_prc ecp on ccp.prc_code=ecp.prc_code and ecp.para_vn=f_get_curver_para_vn('1',left({用户供电单位},7))

left join m_c_cons_contact_rela ccr on cons.id=ccr.cons_id

left join m_c_contact cc on ccr.contact_id=cc.id

left join m_c_cons_cert_rela certr on cons.id=certr.cons_id

left join m_c_cert cert on certr.cert_id=cert.id

left join m_p_code p1 on p1.code_type='custSortCode' and p1.`value`=cons.cons_sort_code

left join m_p_code p2 on p2.code_type='elecTypeCode' and p2.`value`=cons.elec_type_code

left join m_p_code p3 on p3.code_type='ctlMode' and p3.`value`=cons.ctl_mode

left join m_p_code p4 on p4.code_type='statusCode' and p4.`value`=cons.status_code

left join m_p_code p5 on p5.code_type='psVoltCode' and p5.`value`=cons.volt_code

left join m_p_code p6 on p6.code_type='mrModeCode' and p6.`value`=mrpd.mr_mode_code

left join m_p_code p7 on p7.code_type='ruralConsCode' and p7.`value`=cons.rural_cons_code

left join m_p_code p8 on p8.code_type='noteTypeCode' and p8.`value`=cons.note_type_code

where cons.org_no like concat({用户供电单位},'%')

	and if(({费控分类} is null or {费控分类}=''),(1=1),(cons.ctl_mode={费控分类}))

group by cons.cons_no

order by org.`name`,cons.cons_no

-- 文件名：用户档案-费控分类
SELECT

	o1.NAME AS 供电单位,

	cons_no 用户编号,

	cons_name 用户名称,

	c.orgn_cons_no 用户原户号,

	elec_addr 用电地址,

	p5.NAME AS 用户分类,

	p4.NAME AS 用电性质,

	p3.NAME AS 费控分类,

	p2.name AS 用户状态,

	p1.NAME AS 供电电压,

	rs1.CONCAT_WS( '-', id, NAME ) AS 抄表段编号及名称,

	ecp1.CONCAT_WS( '-', prc_code, cat_prc_abbr ) AS 电价码及名称,

	cm1.group_CONCAT( made_no ) AS 所有表号,

	date_format( c.build_date, '%Y-%m-%d' ) 立户时间,

	(

	SELECT NAME

	FROM

		m_p_code

	WHERE

		code_type = 'mrModeCode'

	AND

	VALUE

		= (

		SELECT

			mr.mr_mode_code

		FROM

			m_r_sect r,

			m_r_plan_day mr

		WHERE

			r.id = mr.mr_sect_no

			AND mr.effect_flag = '1'

			AND r.id = c.mr_sect_no

			LIMIT 1

		)

	) 抄表段抄表方式,

	( SELECT CONCAT_WS( '-', line_no, line_NAME ) FROM m_g_line WHERE id = (select line_id from m_c_mp mp where mp.cons_id=c.id and mp.status_code in('01','02','03') and mp.line_id is not null and mp.tg_id is not null

	limit  1)) 线路信息,

		( SELECT CONCAT_WS( '-', tg_no, tg_NAME ) FROM m_g_tg WHERE id = (select tg_id from m_c_mp mp where mp.cons_id=c.id and mp.status_code in('01','02','03') and mp.line_id is not null and mp.tg_id is not null

	limit  1)) 台区信息,

date_format( c.ps_date, '%Y-%m-%d' ) 送电日期

FROM

	m_c_cons c,

	m_c_cons_prc p


LEFT JOIN ac_org o1 ON CODE = c.org_no
LEFT JOIN m_p_code p5 ON code_type = 'custSortCode' AND VALUE = c.cons_sort_code AND take_effect_flag = 1
LEFT JOIN m_p_code p4 ON code_type = 'elecTypeCode' AND VALUE = c.elec_type_code AND take_effect_flag = 1
LEFT JOIN m_p_code p3 ON code_type = 'ctlMode' AND VALUE = c.ctl_mode AND take_effect_flag = 1
LEFT JOIN m_p_code p2 ON code_type = 'statusCode' AND VALUE = c.status_code AND take_effect_flag = 1
LEFT JOIN m_p_code p1 ON code_type = 'psVoltCode' AND VALUE = c.volt_code AND take_effect_flag = 1
LEFT JOIN m_r_sect rs1 ON id = c.mr_sect_no AND rs1.effect_flag = 1
LEFT JOIN m_e_cat_prc ecp1 ON ecp1.para_vn = '40500000021' AND ecp1.prc_code = p.prc_code
LEFT JOIN m_c_meter cm1 ON cons_id = c.id
WHERE

	c.org_no like {用户供电单位}

  and c.ctl_mode not in('01','02','03','04')

	AND c.id = p.cons_id

-- 文件名：费控类型与余额类型对应错误
SELECT

	o1.NAME AS 供电单位,

	c.cons_no 用户编号,

	cons_name 用户名称,

	elec_addr 用电地址,

	p4.NAME AS 用户分类,

	p3.name AS 用户状态,

	rs1.CONCAT_WS( '-', id, NAME ) AS 抄表段编号及名称,

	date_format( c.build_date, '%Y-%m-%d' ) 立户时间,

date_format( c.ps_date, '%Y-%m-%d' ) 送电日期 ,

p2.NAME AS 档案费控分类,

p1.NAME AS 余额类型

FROM

	m_c_cons c,

	m_a_acct_bal b


LEFT JOIN ac_org o1 ON CODE = c.org_no
LEFT JOIN m_p_code p4 ON code_type = 'custSortCode' AND VALUE = c.cons_sort_code AND take_effect_flag = 1
LEFT JOIN m_p_code p3 ON code_type = 'statusCode' AND VALUE = c.status_code AND take_effect_flag = 1
LEFT JOIN m_r_sect rs1 ON id = c.mr_sect_no AND rs1.effect_flag = 1
LEFT JOIN m_p_code p2 ON code_type = 'ctlMode' AND VALUE = c.ctl_mode AND take_effect_flag = 1
LEFT JOIN m_p_code p1 ON code_type = 'prepayCode' AND VALUE = b.bal_type AND take_effect_flag = 1
WHERE

	c.org_no like {用户单位}

  and c.ctl_mode in('01','02','03','04')

	AND c.cons_no = b.cons_no

	and ((c.ctl_mode='01' and b.bal_type<>'04') or(c.ctl_mode='03' and b.bal_type<>'01'))

-- 文件名：本地费控用户联系信息
SELECT

	o1.NAME AS 单位,

	c.cons_no 户号,

	c.cons_name 户名,

	c.elec_addr 用电地址,

	rs1.CONCAT_WS( '|', id, NAME ) AS 抄表段信息,

'' 正确手机号,

	mobile 移动电话,

	office_tel 办公电话,

	homephone 住宅电话,

	(

	SELECT

		user_name

	FROM

		ac_user

	WHERE

		id = (

		SELECT

			f.operator_no

		FROM

			m_r_oper_activity f

		WHERE

			f.effect_flag = 1

			AND f.act_code = '03'

			AND f.mr_sect_no = c.mr_sect_no

			LIMIT 1

		)

	) 抄表员,

	cast(d.id as CHAR(32)) 勿动此列

FROM

	m_c_cons c,

	m_c_cons_contact_rela b,

	m_c_contact d


LEFT JOIN ac_org o1 ON CODE = c.org_no
LEFT JOIN m_r_sect rs1 ON rs1.id = c.mr_sect_no
WHERE

	b.cons_id = c.id

	AND b.contact_id = d.id

	AND ( d.mobile IS NOT NULL OR office_tel IS NOT NULL OR homephone IS NOT NULL )

	AND c.org_no = {供电单位}

	and c.ctl_mode='01'

-- 文件名：用户台区数量查询
select * from (

select

 (select name from ac_org where id=t.org_no LIMIT 1) 单位名称,

 tg_no 台区编码,

 tg_name 台区名称,

 (case pub_priv_flag when '01' then '公变' when '02' then '专变' end) 变压器标志,

line.line_name 线路名称,

 tg_cap 容量,

 count(1) 用户数量

from (

select (select tg_id from m_c_mp c where c.cons_id=cons.id LIMIT 1) tg_id,

(select line_id from m_c_mp c where c.cons_id=cons.id LIMIT 1) line_id,

org_no,status_code from m_c_cons cons

) a left join m_g_tg t on a.tg_id=t.id

left join m_g_line line on a.line_id=line.id

where a.org_no LIKE concat({组织}, '%') and t.run_status_code='01' and status_code='0'

and if(({台区名称} is null or {台区名称}=''),(1=1),(t.tg_name LIKE concat('%',{台区名称}, '%')))

and if(({变压器标志} is null or {变压器标志}=''),(1=1),(t.pub_priv_flag={变压器标志}))

GROUP BY tg_no

) d ORDER BY d.单位名称,d.线路名称,d.台区名称,d.用户数量 DESC

-- 文件名：用户档案电价表号
SELECT

	o1.NAME AS 供电单位,

	cons_no 用户编号,

	cons_name 用户名称,

	elec_addr 用电地址,

	p1.NAME AS 费控分类,

	rs1.CONCAT_WS( '-', id, NAME ) AS 抄表段编号及名称,

	ecp1.CONCAT_WS( '-', prc_code, cat_prc_abbr ) AS 电价码及名称,

	cm1.group_CONCAT( made_no ) AS 所有表号,

	date_format( c.build_date, '%Y-%m-%d' ) 立户时间,

	(

	SELECT NAME

	FROM

		m_p_code

	WHERE

		code_type = 'mrModeCode'

	AND

	VALUE

		= (

		SELECT

			mr.mr_mode_code

		FROM

			m_r_sect r,

			m_r_plan_day mr

		WHERE

			r.id = mr.mr_sect_no

			AND mr.effect_flag = '1'

			AND r.id = c.mr_sect_no

			LIMIT 1

		)

	) 抄表段抄表方式

FROM

	m_c_cons c,

	m_c_cons_prc p


LEFT JOIN ac_org o1 ON CODE = c.org_no
LEFT JOIN m_p_code p1 ON code_type = 'ctlMode' AND VALUE = c.ctl_mode AND take_effect_flag = 1
LEFT JOIN m_r_sect rs1 ON id = c.mr_sect_no AND rs1.effect_flag = 1
LEFT JOIN m_e_cat_prc ecp1 ON ecp1.para_vn = '40500000021' AND ecp1.prc_code = p.prc_code
LEFT JOIN m_c_meter cm1 ON cons_id = c.id
WHERE

c.org_no ={供电单位}

and c.status_code<>'9'

and p.prc_code={电价码编号}

and c.id=p.cons_id

-- 文件名：欠费查询（新）
select

  org.name 单位,

  cons.cons_no 户号,

  cons.orgn_cons_no 原户号,

  cons.cons_name 户名,

  cons.elec_addr 用电地址,

  CONCAT_WS('|', sect.id, sect.NAME) 抄表段信息,

  (

    SELECT

      CONCAT_WS('|', tg_no, tg_name)

    FROM

      m_g_tg

    WHERE

      id in (

        SELECT

          tg_id

        FROM

          m_c_mp mp

        WHERE

          mp.cons_id = cons.id

          and tg_id is not null

      )

    limit

      1

  ) 台区,

  (

    SELECT

      IFNULL(

        CONCAT_WS('|', mobile, office_tel, homephone),

        ''

      )

    FROM

      m_c_cons_contact_rela b,

      m_c_contact d

    WHERE

      b.cons_id = cons.id

      AND b.contact_id = d.id

      AND (

        d.mobile IS NOT NULL

        OR office_tel IS NOT NULL

        OR homephone IS NOT NULL

      )

    limit

      1

  ) 电话,

  us.user_name 抄表员,

  base.t_pq 电量,

  base.rcvbl_amt 电费,

  IFNULL(base.owe_amt, 0) 欠费,

  base.rcvbl_ym 电费年月,

  p1.name 电费类型,

  p2.name 电费类别

from

(

	select

      rcvbl.cons_no,

      (IFNULL(rcvbl.owe_amt, 0) + IFNULL(rcved.this_rcved_amt, 0)) AS owe_amt,

      rcvbl.rcvbl_amt,

      rcvbl.t_pq,

      rcvbl.mr_sect_no,

      rcvbl.org_no,

      rcvbl.rcvbl_ym,

      rcvbl.amt_type,

      rcvbl.ctl_mode

      from

  (

    select

      marf.id rcvbl_amt_id,

      marf.cons_no,

      IFNULL(marf.rcvbl_amt, 0) - IFNULL(marf.rcved_amt, 0) AS owe_amt,

      IFNULL(marf.rcvbl_amt, 0) rcvbl_amt,

      IFNULL(marf.t_pq, 0) t_pq,

      marf.mr_sect_no,

      marf.org_no,

      marf.rcvbl_ym,

      marf.amt_type,

      marf.ctl_mode

    FROM

      m_a_rcvbl_flow_arc marf

    WHERE

      marf.org_no IN (

	SELECT

		ao.id

	FROM

		ac_org ao

	WHERE

		ao.id_path LIKE ( SELECT CONCAT( id_path, '%' ) FROM ac_org WHERE id = {供电单位} )

		)

      AND marf.rcvbl_ym BETWEEN {开始电费年月}

      AND {截止电费年月}

      and marf.ctl_mode={费控类型}

      union all

      select

      marf.id rcvbl_amt_id,

      marf.cons_no,

      IFNULL(marf.rcvbl_amt, 0) - IFNULL(marf.rcved_amt, 0) AS owe_amt,

      IFNULL(marf.rcvbl_amt, 0) rcvbl_amt,

      IFNULL(marf.t_pq, 0) t_pq,

      marf.mr_sect_no,

      marf.org_no,

      marf.rcvbl_ym,

      marf.amt_type,

      marf.ctl_mode

    FROM

      m_a_rcvbl_flow marf

    WHERE

      marf.org_no IN (

	SELECT

		ao.id

	FROM

		ac_org ao

	WHERE

		ao.id_path LIKE ( SELECT CONCAT( id_path, '%' ) FROM ac_org WHERE id = {供电单位} )

		)

      AND marf.rcvbl_ym BETWEEN {开始电费年月}

      AND {截止电费年月}

      and marf.ctl_mode={费控类型}

  ) rcvbl

  LEFT JOIN (

SELECT

      macf.rcvbl_amt_id rcvbl_amt_id,

      sum(IFNULL(macf.this_rcved_amt, 0)) this_rcved_amt

    FROM

      m_a_pay_flow pay

	  inner join m_a_rcved_flow macf on macf.charge_id=pay.id

    WHERE

      pay.charge_date >concat({查询时间},':59')

      and pay.org_no IN (

	SELECT

		ao.id

	FROM

		ac_org ao

	WHERE

		ao.id_path LIKE ( SELECT CONCAT( id_path, '%' ) FROM ac_org WHERE id = {供电单位} )

		)

      AND macf.rcvbl_ym BETWEEN {开始电费年月}

      AND {截止电费年月}

    GROUP BY

      macf.rcvbl_amt_id

  ) rcved ON rcvbl.rcvbl_amt_id = rcved.rcvbl_amt_id

)base

  left join ac_org org on base.org_no = org.code

  left join m_c_cons cons on cons.cons_no = base.cons_no

  left join m_r_sect sect on sect.id = base.mr_sect_no

  left join m_r_oper_activity oper on oper.mr_sect_no = sect.id

  and oper.act_code = '03'

  and oper.effect_flag = '1'

  left join ac_user us on us.id = oper.operator_no

  left join m_p_code p1 on p1.code_type = 'ctlMode'

  and p1.value = base.ctl_mode

  left join m_p_code p2 on p2.code_type = 'paTypeCode'

  and p2.value = base.amt_type

  where

	base.owe_amt != 0

-- 文件名：江源欠费(冻结、按单位汇总)
select o.id 单位编码,o.`name` 单位名称,ifnull(t.owe_amt,0) 电费欠费

from ac_org o

join (

	select t1.org_no,sum(t1.owe_amt) owe_amt

	from (

		select a.id,a.org_no,a.cons_no,a.rcvbl_amt,sum(b.this_rcved_amt) rcved_amt,a.rcvbl_amt-ifnull(sum(b.this_rcved_amt),0) owe_amt

		from m_a_rcvbl_flow a

    left join m_a_rcved_flow b on a.id=b.rcvbl_amt_id and b.rcved_date<={截止日期}

		where a.org_no like concat({供电单位},'%')

			and a.release_date<=date_format({截止日期},'%Y%m%d')

			and not exists(select id from m_a_rcvbl_flow_arc where org_no like concat({供电单位},'%') and id=a.id)

			and (a.rcved_amt is not null)

		group by a.id,a.org_no,a.cons_no,a.rcvbl_amt

    having (a.rcvbl_amt-ifnull(sum(b.this_rcved_amt),0)<>0)

    union all

		select a.id,a.org_no,a.cons_no,a.rcvbl_amt,sum(b.this_rcved_amt) rcved_amt,a.rcvbl_amt-ifnull(sum(b.this_rcved_amt),0) owe_amt

		from m_a_rcvbl_flow_arc a

    left join m_a_rcved_flow b on a.id=b.rcvbl_amt_id and b.rcved_date<={截止日期}

		where a.org_no like concat({供电单位},'%')

			and a.release_date<=date_format({截止日期},'%Y%m%d')

			and (a.rcved_amt is not null)

		group by a.id,a.org_no,a.cons_no,a.rcvbl_amt

    having (a.rcvbl_amt-ifnull(sum(b.this_rcved_amt),0)<>0)

  ) t1

  group by t1.org_no

) t on o.id=t.org_no

where o.id like concat({供电单位},'%')

-- 文件名：江源欠费(冻结、按用户汇总)
select t1.org_no as 单位编码,t1.org_name as 单位名称,t1.cons_no as 户号,cons.cons_name as 户名

	,sum(t1.rcvbl_amt-ifnull(t2.amt,0)) as 电费欠费

from (

	select a.org_no,a.org_name,a.cons_no,sum(a.rcvbl_amt) rcvbl_amt

	from (

		select a.org_no,o.`name` as org_name,a.cons_no,sum(a.rcvbl_amt) rcvbl_amt

		from m_a_rcvbl_flow a

		join ac_org o on a.org_no=o.id

		where a.org_no like concat({供电单位},'%')

			and a.release_date<=date_format({截止日期},'%Y%m%d')

			and (a.rcved_amt is not null)

		group by a.cons_no

		union all

		select a.org_no,o.`name` as org_name,a.cons_no,sum(a.rcvbl_amt) rcvbl_amt

		from m_a_rcvbl_flow_arc a

		join ac_org o on a.org_no=o.id

		where a.org_no like concat({供电单位},'%')

			and a.release_date<=date_format({截止日期},'%Y%m%d')

			and not exists(select id from m_a_rcvbl_flow where org_no like concat({供电单位},'%') and id=a.id)

			and (a.rcved_amt is not null)

		group by a.cons_no

	) a

	group by a.cons_no

) t1

left join (

	select a.cons_no,sum(a.this_rcved_amt) amt

	from m_a_rcved_flow a

	where a.org_no like concat({供电单位},'%')

		and a.rcved_date<={截止日期}

		and (a.this_in_price_amt is not null)

	group by a.cons_no

) t2 on t1.cons_no=t2.cons_no

left join m_c_cons cons on t1.cons_no=cons.cons_no

where t1.rcvbl_amt-ifnull(t2.amt,0)<>0

group by t1.org_no,t1.cons_no

-- 文件名：后付费用户负余额信息
SELECT

	o1.NAME AS 供电单位,

	c.cons_no 用户编号,

	cons_name 用户名称,

	p4.NAME AS 用户分类,

	p3.NAME AS 档案费控分类,

	p2.NAME AS 供电电压,

	rs1.CONCAT_WS( '-', id, NAME ) AS 抄表段编号及名称,

	(

	SELECT NAME

	FROM

		m_p_code

	WHERE

		code_type = 'mrModeCode'

	AND

	VALUE

		= (

		SELECT

			mr.mr_mode_code

		FROM

			m_r_sect r,

			m_r_plan_day mr

		WHERE

			r.id = mr.mr_sect_no

			AND mr.effect_flag = '1'

			AND r.id = c.mr_sect_no

			LIMIT 1

		)

	) 抄表段抄表方式 ,

	p.prepay_bal 当前余额,

	p1.name AS 余额类型

FROM

	m_c_cons c,

	m_a_acct_bal p


LEFT JOIN ac_org o1 ON CODE = c.org_no
LEFT JOIN m_p_code p4 ON code_type = 'custSortCode' AND VALUE = c.cons_sort_code AND take_effect_flag = 1
LEFT JOIN m_p_code p3 ON code_type = 'ctlMode' AND VALUE = c.ctl_mode AND take_effect_flag = 1
LEFT JOIN m_p_code p2 ON code_type = 'psVoltCode' AND VALUE = c.volt_code AND take_effect_flag = 1
LEFT JOIN m_r_sect rs1 ON id = c.mr_sect_no AND rs1.effect_flag = 1
LEFT JOIN m_p_code p1 ON code_type ='prepayCode' and value=p.bal_type AND take_effect_flag = 1
WHERE

	c.org_no like {供电单位}

	AND c.ctl_mode='03'

	AND p.prepay_bal<0

	AND c.cons_no= p.cons_no

-- 文件名：磁卡用户余额
SELECT

	con.cons_name 户名,

	con.cons_no 户号,

	og.NAME 供电所,

	IFNULL( ba.prepay_bal, 0 ) 当前余额

FROM

	m_a_acct_bal ba

	LEFT JOIN ac_org og ON ba.org_no = og.

	CODE LEFT JOIN m_c_cons con ON ba.cons_no = con.cons_no

WHERE

	ba.org_no LIKE '5100109%'

	AND ba.bal_type = '04';

-- 文件名：用户余额对比
select org.`name` 供电单位,c.cons_no 户号,l.line_name 线路,tg.tg_name 台区,c.cons_name 户名,cm.made_no 表号,p1.`name` 费控类型,mr.mr_read 电表示数,a.prepay_bal 账户余额,i.meterPurchaseNum 账户购电次数,d.remainMoney 电表余额,d.buyNum 电表购电次数,d.settlementDate 结算日期,d.settlementRemainMoney 结算日电表余额,d.settlementBuyNum 结算日次数,ROUND((IFNULL(a.prepay_bal,0)-IFNULL(d.settlementRemainMoney,0)-IFNULL(t.dbwb,0)),2 ) 余额差,t.dbwb 低五未写卡,last1ps.iccardFee 最后一次写卡金额

,(case when i.meterPurchaseNum-d.settlementBuyNum=1 then ROUND((IFNULL(a.prepay_bal,0)-IFNULL(d.settlementRemainMoney,0)-IFNULL(t.dbwb,0)),2 )- last1ps.iccardFee else 0 end) 次数差一的余额差

from m_c_cons c

join ac_org org on c.org_no = org.id

join m_c_mp mp on c.id = mp.cons_id and mp.type_code='01' and mp.status_code in ('01','02')

join m_c_meter cm on c.id = cm.cons_id and mp.id=cm.mp_id

join m_c_meter_read mr on cm.id = mr.meter_id and mr.read_type_code='11'

JOIN m_r_coll_obj o on c.id = o.cons_id and o.mp_id=mp.id and o.meter_id=cm.id

JOIN m_r_cp_comm_para p on (o.cp_no = p.cp_no)

JOIN m_a_acct_bal a on a.cons_no = c.cons_no

join m_ps_iccard_info i on c.cons_no = i.consCode and i.iccardStatus="02"

left JOIN m_r_cons_balance_day d on (p.area_code = d.region and p.terminal_addr = d.`local` and d.pn = o.coll_port)

and if(({时间} is null or {时间}=''),(1=1),d.createDate ={时间})



left join m_g_line l on mp.line_id = l.id

left join m_g_tg tg on mp.tg_id = tg.id

left join m_p_code p1 on p1.code_type="ctlMode" and p1.`value`=c.ctl_mode



left join (select cons_no,

sum(case when ifnull(category,'') in ('03','04')  then adjustment_amt else 0 end) 'dbwb'

from m_kb_a_card_classpq where  if(({组织} is null or {组织}=''),(1=1),org_no like CONCAT({组织},'%')) and deal_flag='01' group by cons_no) t on t.cons_no = c.cons_no



left join (select b.conscode cons_no,b.iccardFee from m_ps_purchase b

join (select conscode,max(tradeTime) tradeTime from m_ps_purchase where orgid like concat({组织}, '%') and isNew='01' group by conscode) b1 on b.conscode=b1.conscode and b.tradeTime=b1.tradeTime

where orgid like concat({组织}, '%') and isNew='01'

) last1ps on c.cons_no=last1ps.cons_no

where  if(({组织} is null or {组织}=''),(1=1),c.org_no like concat({组织}, '%'))

and if(({户号} is null or {户号}=''),(1=1),c.cons_no={户号})

and if(({抄表段编号} is null or {抄表段编号}=''),(1=1),c.mr_sect_no like CONCAT({抄表段编号},'%'))

-- 文件名：用户综合信息查询
select distinct o.name 单位名称,cons.id 用户ID,

  cons.cons_no 用户编号,cons.cons_name 用户名称,

  cons.orgn_cons_no 用户原户号,cons.elec_addr 用电地址,

  p1.`name` 用户分类,p2.`name` 行业分类,p3.`name` 供电电压,p4.`name` 费控分类,cons.contract_cap 合同容量,cons.run_cap 运行容量,

  rs1.CONCAT_WS( '|', id, NAME ) AS 抄表段,

  (select group_concat(distinct y.mobile) from m_c_cons_contact_rela x join m_c_contact y on x.contact_id=y.id where x.cons_id=cons.id and ifnull(y.mobile,'')<>'') 电话号码,

  p5.`name` 电价用电类别,prc.cat_prc_name 执行电价,line.line_no 线路编码,

  line.line_name 线路,tq.tg_no 台区编码,tq.tg_name 台区,

  meter.made_no 出厂编号,m_read.mr_read 示数,meter.t_factor 综合倍率,

  p6.`name` 型号,p7.`name` 表计类别,p8.`name` 表计类型,p9.`name` 表计电流,p10.`name` 表计相数,meter.inst_date 安装日期,dm.made_date 出厂日期

from m_c_cons cons

join ac_org o on o.id=cons.org_no

join ac_org po on left(o.id,7)=po.id

left join m_c_sp sp on cons.id=sp.cons_id

left join m_c_mp mp on sp.id=mp.sp_id and mp.meter_flag='1' and mp.status_code in('01','02')

left join m_c_meter meter on mp.id=meter.mp_id

left join m_d_meter dm on meter.id=dm.id

left join m_c_meter_read m_read on meter.id=m_read.meter_id and m_read.read_type_code='11'

left join m_c_cons_prc consprc on mp.tariff_id=consprc.id

left join m_e_cat_prc prc on consprc.prc_code=prc.prc_code and prc.para_vn=f_get_curver_para_vn('1', left({组织},7))

left join m_g_tg tq on tq.id=mp.tg_id

left join m_g_line line on line.id=mp.line_id

left join m_p_code p1 on p1.code_type='custSortCode' and p1.`value`=cons.cons_sort_code

left join m_p_code p2 on p2.code_type='tradeCode' and p2.`value`=cons.trade_code

left join m_p_code p3 on p3.code_type='psVoltCode' and p3.`value`=cons.volt_code

left join m_p_code p4 on p4.code_type='ctlMode' and p4.`value`=cons.ctl_mode

left join m_p_code p5 on p5.code_type='elecTypeCode' and p5.`value`=consprc.elec_type_code

left join m_p_code p6 on p6.code_type='meterModelNo' and p6.`value`=meter.model_code

left join m_p_code p7 on p7.code_type='meterSort' and p7.`value`=meter.sort_code

left join m_p_code p8 on p8.code_type='meterTypeCode' and p8.`value`=meter.type_code

left join m_p_code p9 on p9.code_type='meterRcSort' and p9.`value`=meter.rated_current

left join m_p_code p10 on p10.code_type='wiringMode' and p10.`value`=meter.wiring_mode


LEFT JOIN m_r_sect rs1 ON rs1.id = cons.mr_sect_no
where cons.org_no like concat({组织}, '%')

 and cons.status_code<>'9'

 and if(({抄表段编号} is null or {抄表段编号}=''),(1=1),(cons.mr_sect_no={抄表段编号}))

 and if(({台区名称} is null or {台区名称}=''),(1=1),(tq.tg_name like concat('%',{台区名称}, '%')))

 and if(({线路名称} is null or {线路名称}=''),(1=1),(line.line_name like concat('%',{线路名称}, '%')))

 and if(({户名} is null or {户名}=''),(1=1),cons.cons_name like CONCAT('%',{户名},'%'))

 and if(({户号} is null or {户号}=''),(1=1),cons.cons_no like CONCAT('%',{户号},'%'))

 and if(({出厂编号} is null or {出厂编号}=''),(1=1),meter.made_no like CONCAT('%',{出厂编号},'%'))

 and if(({费控分类} is null or {费控分类}=''),(1=1),cons.ctl_mode ={费控分类})

order by cons.org_no,line.line_name,tq.tg_name,cons.mr_sect_no,cons.cons_no,cons.cons_name

-- 文件名：用户发行电量电费及开票信息
select o.name 单位,d.id 抄表段编号,d.name 抄表段名称,cons.cons_no 户号,cons.cons_name 户名,cons.elec_addr 用电地址,p2.name 票据类型,cm.made_no 表号,rd.t_factor 综合倍率,last_mr_num 起度,this_read 止度,df.ym 账期,总电量,总电费,qf.rcvbl_amt 应收电费,qf.rcved_amt 实收电费,p3.name 电费结清的标志

,p4.name 票据打印类型,fp.print_amt 票据打印金额,fp.print_num 票据打印次数,fp.print_date 票据打印时间

,(case when note.note_qf_id is null then '否' else '是' end) 是否开具电子发票,ifnull(billing_date,'') 电子发票开票时间

from m_c_cons cons

join ac_org o on cons.org_no=o.id and o.id like concat({组织}, '%')

join m_c_mp mp on cons.id=mp.cons_id and mp.type_code='01' and mp.status_code in ('01','02')

join m_c_meter cm on mp.id=cm.mp_id and mp.cons_id=cm.cons_id

join (select a.id,a.ym,a.cons_id,a.cons_no,sum(t_settle_pq) 总电量,sum(t_amt) 总电费

from m_e_cons_snap_arc a

join m_e_cons_prc_amt_arc b on a.id=b.calc_id

where a.org_no like concat({组织}, '%') and a.ym={电费年月}

group by a.id,a.ym,a.cons_id,a.cons_no

) df on cons.id=df.cons_id and cons.cons_no=df.cons_no and (总电量<>0 or 总电费<>0)

join (select calc_id,cons_no,mp_id,meter_id,last_mr_num,this_read,t_factor from m_r_data_arc where org_no like concat({组织}, '%') and read_type_code='11' and amt_ym={电费年月} group by calc_id,cons_no,mp_id,meter_id,last_mr_num,this_read,t_factor

) rd on cons.cons_no=rd.cons_no and rd.mp_id = mp.id and cm.id=rd.meter_id and rd.calc_id = df.id

left join m_r_sect d on cons.mr_sect_no=d.id

left join (select id,cons_no,calc_id,settle_flag,rcvbl_amt,rcved_amt from m_a_rcvbl_flow where rcvbl_ym={电费年月} and org_no like concat({组织}, '%') and id not in (select id from m_a_rcvbl_flow_arc where rcvbl_ym={电费年月} and org_no like concat({组织}, '%'))

union all

select id,cons_no,calc_id,settle_flag,rcvbl_amt,rcved_amt from m_a_rcvbl_flow_arc where rcvbl_ym={电费年月} and org_no like concat({组织}, '%')

) qf on df.cons_no=qf.cons_no and df.id=qf.calc_id

left join (select e.rcvbl_amt_id,g.note_type_code,print_amt,max(print_num) print_num,max(e.print_date) print_date

from m_a_inv_print_flow e

join m_a_inv f on e.note_id=f.id

join m_a_inv_ver g on f.ver_id=g.id

where e.org_no like concat({组织}, '%')

group by rcvbl_amt_id,g.note_type_code,print_amt

) fp on qf.id=fp.rcvbl_amt_id

left join (select cons_no,billing_date,rela_ids note_qf_id from m_a_note_info lateral where org_no like concat({组织}, '%') and status='01') note on note.cons_no=cons.cons_no and note.note_qf_id like concat('%',qf.id,'%')

left join m_p_code p2 on p2.code_type='noteTypeCode' and p2.value=cons.note_type_code

left join m_p_code p3 on p3.code_type='amtSettleFlag' and p3.value=qf.settle_flag

left join m_p_code p4 on p4.code_type='noteTypeCode' and p4.value=fp.note_type_code

where cons.status_code<>'9'

order by 单位,抄表段编号,户号

-- 文件名：工商业电价明细核对
select o1.`name` AS 公司名称

  ,convert(a.para_vn,char) 版本号,a.prc_code 电价编码,a.cat_prc_name 电价名称

	,p1.`name` 用电类别,p2.`name` 电压等级

  ,p3.`name` 执行范围分类,p4.`name` 电价时段

  ,b.cat_kwh_prc 目录电度电价,b.kwh_prc 电度电价

  ,@prc:=(select kwh_prc from m_e_cat_prc x join m_e_cat_prc_det y on x.id=y.cat_prc_id and x.para_vn={参考电价版本号} where x.prc_code=a.prc_code and y.range_type_code=b.range_type_code and y.prc_ti_code=b.prc_ti_code) 参考电度电价

  ,if(b.kwh_prc<>ifnull(@prc,0),'是','否') 差异

  ,eap7.sum(pl_prc) AS 农网还贷

  ,eap6.sum(pl_prc) AS 水利基金

  ,eap5.sum(pl_prc) AS 库区移民基金

  ,eap4.sum(pl_prc) AS 可再生能源

  ,eap3.sum(pl_prc) AS 可再生能源（灾区）

  ,eap2.sum(pl_prc) AS 电能替代过网费

  ,eap1.sum(pl_prc) AS 代征合计

  ,ecdi4.sum(trans_dist_prc) AS 输配合计

  ,ecdi3.sum(agent_prc) AS 代理合计

  ,ecdi2.sum(content3) AS 上网环节线损合计

  ,ecdi1.sum(content4) AS 系统运行费合计

  ,e.cap_prc 容量单价,e.dmd_prc 需量单价

from m_e_cat_prc a

join m_e_cat_prc_det b on a.id=b.cat_prc_id

left join m_e_base_prc e on a.id=e.cat_prc_id

left join m_p_code p1 on p1.code_type='elecTypeCode' and p1.`value`=a.elec_type_code

left join m_p_code p2 on p2.code_type='prcVoltCode' and p2.`value`=a.prc_volt_code

left join m_p_code p3 on p3.code_type='rangeTypeCode' and p3.`value`=b.range_type_code

left join m_p_code p4 on p4.code_type='prcTsCode' and p4.`value`=b.prc_ti_code


LEFT JOIN ac_org o1 ON id=left(a.org_no,7)
LEFT JOIN m_e_add_pl_prc eap7 ON det_id=b.id and pl_code='10000'
LEFT JOIN m_e_add_pl_prc eap6 ON det_id=b.id and pl_code='20000'
LEFT JOIN m_e_add_pl_prc eap5 ON det_id=b.id and pl_code='30000'
LEFT JOIN m_e_add_pl_prc eap4 ON det_id=b.id and pl_code='40000'
LEFT JOIN m_e_add_pl_prc eap3 ON det_id=b.id and pl_code='40001'
LEFT JOIN m_e_add_pl_prc eap2 ON det_id=b.id and pl_code='90000'
LEFT JOIN m_e_add_pl_prc eap1 ON det_id=b.id and ifnull(prc_io_flag,'')<>'03'
LEFT JOIN m_e_cat_prc_det_items ecdi4 ON para_vn=a.para_vn and prc_id=a.id and det_id=b.id
LEFT JOIN m_e_cat_prc_det_items ecdi3 ON para_vn=a.para_vn and prc_id=a.id and det_id=b.id
LEFT JOIN m_e_cat_prc_det_items ecdi2 ON det_id=b.id
LEFT JOIN m_e_cat_prc_det_items ecdi1 ON det_id=b.id
where a.para_vn={核对电价版本号}

  and left(a.elec_type_code,1) in('1','4')

  and a.prc_code like '400%'

order by 公司名称,a.para_vn,a.prc_code,b.range_type_code,b.prc_ti_code

-- 文件名：疫情期间优惠
SELECT

	b.prc_code 电费年月,

	o2.NAME AS 分公司,

	a.org_no 单位编码,

	o1.NAME AS 供电所,

	a.mr_sect_no 抄表段,

	a.cons_no 户号,

	a.cons_name 户名,

	p1.NAME AS 行业类别,

	( - 1 ) * b.amt 优惠电费

FROM

	m_c_cons a,

	m_e_cons_calc_data b


LEFT JOIN ac_org o2 ON o2.id = substring( a.org_no, 1, 7 )
LEFT JOIN ac_org o1 ON o1.id = a.org_no
LEFT JOIN m_p_code p1 ON code_type = 'tradeCode' AND VALUE = a.trade_code AND take_effect_flag = 1
WHERE

	a.cons_no = b.cons_no

and b.info_type='YQYH'

	AND b.prc_code ={电费年月}

	AND a.org_no ={供电单位}

-- 文件名：按电价查询发行电费
SELECT

	供电单位,

	用户编号,用户名称,用电地址,用户分类,费控分类,供电电压,抄表段编号及名称,所有表号,电费年月,发行总电量,发行总电费

FROM

	(

	SELECT

		( SELECT NAME FROM ac_org WHERE CODE = c.org_no ) 供电单位,

		c.cons_no 用户编号,

		c.cons_name 用户名称,

		c.elec_addr 用电地址,

		( SELECT NAME FROM m_p_code WHERE code_type = 'custSortCode' AND VALUE = c.cons_sort_code ) 用户分类,

		( SELECT NAME FROM m_p_code WHERE code_type = 'ctlMode' AND VALUE = c.ctl_mode ) 费控分类,

		( SELECT NAME FROM m_p_code WHERE code_type = 'psVoltCode' AND VALUE = c.volt_code ) 供电电压,

		( SELECT CONCAT_WS( '-', id, NAME ) FROM m_r_sect ff WHERE id = c.mr_sect_no AND ff.effect_flag = 1 ) 抄表段编号及名称,

		( SELECT group_CONCAT( made_no ) FROM m_c_meter cm WHERE cons_id = c.id ) 所有表号,

		a.rcvbl_ym 电费年月,

		a.t_pq 发行总电量,

		a.rcvbl_amt 发行总电费

	FROM

		m_a_rcvbl_flow a,

		m_c_cons c

	WHERE

		a.cons_no = c.cons_no

		AND a.org_no = c.org_no

		AND a.rcvbl_ym ={电费年月}

		AND a.org_no LIKE CONCAT({供电单位}, '%' )

		AND a.calc_id IN (

		SELECT

			calc_id

		FROM

			m_e_cons_prc_amt_arc prcamt

		WHERE

			id IN ( SELECT prc_amt_id FROM m_e_kwh_amt_arc kwh WHERE kwh.org_no LIKE CONCAT({供电单位}, '%' ) AND kwh.kwh_prc = {电价单价})

			AND prcamt.ym ={电费年月}

			AND prcamt.org_no LIKE CONCAT({供电单位}, '%' )

		) UNION ALL

	SELECT

		( SELECT NAME FROM ac_org WHERE CODE = c.org_no ) 供电单位,

		c.cons_no 用户编号,

		c.cons_name 用户名称,

		c.elec_addr 用电地址,

		( SELECT NAME FROM m_p_code WHERE code_type = 'custSortCode' AND VALUE = c.cons_sort_code ) 用户分类,

		( SELECT NAME FROM m_p_code WHERE code_type = 'ctlMode' AND VALUE = c.ctl_mode ) 费控分类,

		( SELECT NAME FROM m_p_code WHERE code_type = 'psVoltCode' AND VALUE = c.volt_code ) 供电电压,

		( SELECT CONCAT_WS( '-', id, NAME ) FROM m_r_sect ff WHERE id = c.mr_sect_no AND ff.effect_flag = 1 ) 抄表段编号及名称,

		( SELECT group_CONCAT( made_no ) FROM m_c_meter cm WHERE cons_id = c.id ) 所有表号,

		a.rcvbl_ym 电费年月,

		a.t_pq 发行总电量,

		a.rcvbl_amt 发行总电费

	FROM

		m_a_rcvbl_flow_arc a,

		m_c_cons c

	WHERE

		a.cons_no = c.cons_no

		AND a.org_no = c.org_no

		AND a.rcvbl_ym ={电费年月}

		AND a.org_no LIKE CONCAT({供电单位}, '%' )

		AND a.calc_id IN (

		SELECT

			calc_id

		FROM

			m_e_cons_prc_amt_arc prcamt

		WHERE

			id IN ( SELECT prc_amt_id FROM m_e_kwh_amt_arc kwh WHERE kwh.org_no LIKE CONCAT({供电单位}, '%' ) AND kwh.kwh_prc = {电价单价} )

			AND prcamt.ym ={电费年月}

			AND prcamt.org_no LIKE CONCAT({供电单位}, '%' )

		)

	)  ff

ORDER BY

	ff.供电单位,

	ff.用户编号

-- 文件名：电费查询
SELECT

	o1.NAME AS 单位名称,

	p1.NAME AS 城农网标志,

	cons.cons_name 用户名称,

	cons.cons_no 用户编号,

	flow.rcvbl_ym  电费年月,

	flow.t_pq 电量,

	flow.rcvbl_amt 电费,

	catprc.cat_prc_name 电价名称

FROM

	m_c_cons cons

	join m_a_rcvbl_flow flow on cons.cons_no = flow.cons_no

	join m_c_cons_prc prc on cons.id = prc.cons_id

	join m_e_cat_prc catprc on prc.prc_code = catprc.prc_code and catprc.para_vn =f_get_curver_para_vn('1', cons.org_no)


LEFT JOIN ac_org o1 ON CODE = cons.org_no
LEFT JOIN m_p_code p1 ON p1.code_type='ruralConsCode' and cons.rural_cons_code=p1.`value` AND take_effect_flag = 1
WHERE

cons.rural_cons_code = {城农网标志}

AND cons.org_no = {供电单位}

and flow.rcvbl_ym ={电费年月}

-- 文件名：同时存在欠费和余额
SELECT

	o1.NAME AS 单位,

	a.cons_no 户号,

	c.cons_name 户名,

	c.elec_addr 用电地址,

	rs1.CONCAT_WS( '|', id, NAME ) AS 抄表段,

	a.t_pq 电量,

	a.rcvbl_amt 电费,

	( a.rcvbl_amt - a.rcved_amt ) 欠费,

	b.prepay_bal 余额,

	p2.NAME AS 余额类型,

	a.rcvbl_ym 电费年月,

	p1.NAME AS 电费类型

FROM

	m_c_cons c,

	m_a_rcvbl_flow a,

  m_a_acct_bal b


LEFT JOIN ac_org o1 ON CODE = a.org_no
LEFT JOIN m_r_sect rs1 ON rs1.id = a.mr_sect_no
LEFT JOIN m_p_code p2 ON code_type = 'prepayCode' AND VALUE = b.card_bal AND take_effect_flag = 1
LEFT JOIN m_p_code p1 ON code_type = 'ctlMode' AND VALUE = a.ctl_mode AND take_effect_flag = 1
WHERE

	a.cons_no = c.cons_no

	and b.cons_no=c.cons_no

	and b.prepay_bal>0

	AND a.rcvbl_amt <> 0

	and a.settle_flag<>'03'

	AND a.rcvbl_ym ={电费年月}

	AND a.org_no like {供电单位}

ORDER BY a.org_no,a.cons_no

-- 文件名：采集用户电量电费查询
SELECT

	a.cons_no 户号,

	a.cons_name 用户名称,

	a.elec_addr 用电地址,

	(

		SELECT

			SUM(t_settle_pq)

		FROM

			m_e_cons_prc_amt_arc amt,

			m_e_cons_snap_arc b

		WHERE

			amt.calc_id = b.id

		AND b.ym ={ 年月 }

		AND b.org_no = { 供电单位 }

		AND b.cons_id = a.id

	) 电量,

	(

		SELECT

			SUM(t_amt)

		FROM

			m_e_cons_prc_amt_arc amt,

			m_e_cons_snap_arc b

		WHERE

			amt.calc_id = b.id

		AND b.ym ={ 年月 }

		AND b.org_no = { 供电单位 }

		AND b.cons_id = a.id

	) 电费,

	p1.`name` AS 发票类型,

	'' 税率,

	'' 发票张数

FROM

	m_c_cons a,

	m_r_cp_cons_rela e,

	m_r_cp b,

	m_r_coll_obj c,

	m_c_meter d


LEFT JOIN m_p_code p1 ON p1.`value` = a.note_type_code AND p1.code_type = 'noteTypeCode' AND take_effect_flag = 1
WHERE

	a.id = d.cons_id

AND a.id = e.cons_id

AND e.cp_no = b.cp_no

AND b.cp_no = c.cp_no

AND c.meter_id = d.id

AND a.org_no ={ 供电单位 }

-- 文件名：应实未查询
select o1.name AS 供电单位,ys.*,b.实收电费,c.欠费

from (

	SELECT

		a.ym 电费年月,

		sum(ifnull(c.t_settle_pq, 0)) 总电量,

		sum(ifnull(c.t_amt, 0)) 应收电费

	FROM

		m_e_Cons_Snap_Arc a

	JOIN m_c_cons acons ON a.cons_id = acons.id

	LEFT JOIN ac_org co ON a.org_no = co. CODE

	LEFT JOIN m_e_Consprc_Snap_Arc b ON a.id = b.calc_id

	LEFT JOIN m_e_Cons_Prc_Amt_Arc c ON a.id = c.calc_id

	WHERE b.id = c.prc_snap_id

	AND a.org_no LIKE concat({供电单位}, '%')

	AND b.org_no LIKE concat({供电单位}, '%')

	AND c.org_no LIKE concat({供电单位}, '%')

	AND ifnull(c.Elec_Type_Code, 0) <> '000' --  排除零电价

	AND IFNULL(b.Data_Src, '01') NOT IN ('98', '99')

	AND (c.t_settle_pq <> 0 OR c.t_amt <> 0)

	AND a.ym >= {开始电费年月}

	AND a.ym <= {截止电费年月}

	GROUP BY a.ym

) ys

LEFT JOIN

(

	SELECT

		rcvbl_ym 电费年月,

		SUM(ifnull(this_rcved_amt,0)) 实收电费

	FROM

		m_a_rcved_flow

	WHERE org_no LIKE concat({供电单位}, '%')

	AND rcvbl_ym >= {开始电费年月}

	AND rcvbl_ym <= {截止电费年月}

	GROUP BY rcvbl_ym

) b

on ys.电费年月=b.电费年月

LEFT JOIN

(SELECT

  rcvbl_ym 电费年月,

	sum(ifnull((rcvbl_amt - rcved_amt ),0)) 欠费

FROM

	m_a_rcvbl_flow


LEFT JOIN ac_org o1 ON code ={供电单位}
WHERE

  rcvbl_amt<>0

	and settle_flag<>'03'

        and org_no like CONCAT({供电单位},'%')

	AND rcvbl_ym >= {开始电费年月}

	AND rcvbl_ym <= {截止电费年月}

GROUP BY rcvbl_ym) c

on ys.电费年月=c.电费年月

-- 文件名：长宁用户电量电费_在途
select o.name 单位,d.id 抄表段编号,d.name 抄表段名称,cons.cons_no 户号,cons.cons_name 户名,prc_code 电价编码,cat_prc_name 电价名称,p1.name 电价用电类别,p4.name 电价行业类别, df.总电量 总电量,df.总电费 总电费,e.this_cont_amt 优惠电费

from m_c_cons cons

join ac_org o on cons.org_no=o.id and o.id like concat({组织},'%')

left join (select a.id calc_id,a.cons_id,c.prc_code,c.cat_prc_name,b.elec_type_code,b.trade_type_code,sum(b.t_settle_pq) 总电量,sum(b.t_amt)总电费

from m_r_plan plan

join m_e_cons_snap a on plan.app_no=a.app_code

join m_e_cons_prc_amt b on a.id=b.calc_id

join m_e_cat_prc c on b.prc_code=c.prc_code and b.para_vn=c.para_vn

where plan.event_type='001' and a.ym={电费年月} and a.org_no like concat({组织},'%')

group by a.id,a.cons_id,c.prc_code,c.cat_prc_name

) df on cons.id=df.cons_id

left join m_e_cont_fee e on df.calc_id=e.calc_id

left join m_r_sect d on cons.mr_sect_no=d.id

left join m_p_code p1 on p1.code_type='electypecode' and p1.value=df.elec_type_code

left join m_p_code p4 on p4.code_type='tradecode' and p4.value=df.trade_type_code

order by 1,2,4

-- 文件名：电价电量电费统计
select p.cat_prc_name 电价名称,ty.prc_code 电价编号,ty.sumbypq 当期电量,ty.sumbyamt 当期电费,ty.sumqnpq 去年电量,ty.sumqnamt 去年电费,ty.sumsypq 上期电量,ty.sumsyamt 上期电费 from (

(select "1" sumtype,t.prc_code,t.sumbypq,t.sumbyamt,t1.sumqnpq,t1.sumqnamt,t2.sumsypq,t2.sumsyamt from

(select prc_code,sum(t_settle_pq) sumbypq,sum(t_amt) sumbyamt from m_e_cons_prc_amt_arc where org_no like concat({供电单位}, '%') and ym>={开始年月} and ym <={结束年月} group by prc_code) t

left join

(select prc_code,sum(t_settle_pq) sumqnpq,sum(t_amt) sumqnamt from m_e_cons_prc_amt_arc

where org_no like concat({供电单位}, '%') and ym=date_format((CONCAT({开始年月},"01")- INTERVAL 1 YEAR),'%Y%m')

and PERIOD_DIFF( date_format(CONCAT({结束年月},"01"),'%Y%m' ) ,date_format(CONCAT({开始年月},"01"),'%Y%m'))=0

group by prc_code) t1 on t.prc_code=t1.prc_code

left join

(select prc_code,sum(t_settle_pq) sumsypq,sum(t_amt) sumsyamt from m_e_cons_prc_amt_arc

where org_no like concat({供电单位}, '%') and ym=date_format(DATE_SUB(CONCAT({开始年月},"01"), INTERVAL 1 MONTH),'%Y%m')

 and PERIOD_DIFF( date_format(CONCAT({结束年月},"01"),'%Y%m' ) ,date_format(CONCAT({开始年月},"01"),'%Y%m'))=0

group by prc_code) t2 on t.prc_code=t2.prc_code)

UNION All

(select y.sumtype,"合计" prc_code, y.sumbypq,y.sumbyamt,y1.sumqnpq,y1.sumqnamt,y2.sumsypq,y2.sumsyamt from

(select "2" sumtype, sum(t_settle_pq) sumbypq,sum(t_amt) sumbyamt from m_e_cons_prc_amt_arc where org_no like concat({供电单位}, '%') and  ym>={开始年月} and ym <={结束年月}) y

left join

(select "2" sumtype, sum(t_settle_pq) sumqnpq,sum(t_amt) sumqnamt  from m_e_cons_prc_amt_arc

where org_no like concat({供电单位}, '%') and ym=date_format((CONCAT({开始年月},"01")- INTERVAL 1 YEAR),'%Y%m')

 and PERIOD_DIFF( date_format(CONCAT({结束年月},"01"),'%Y%m' ) ,date_format(CONCAT({开始年月},"01"),'%Y%m'))=0) y1 on y.sumtype=y1.sumtype

left join

(select "2" sumtype, sum(t_settle_pq) sumsypq,sum(t_amt) sumsyamt from m_e_cons_prc_amt_arc

where org_no like concat({供电单位}, '%') and ym=date_format(DATE_SUB(CONCAT({开始年月},"01"), INTERVAL 1 MONTH),'%Y%m')

 and PERIOD_DIFF( date_format(CONCAT({结束年月},"01"),'%Y%m' ) ,date_format(CONCAT({开始年月},"01"),'%Y%m'))=0) y2 on y.sumtype=y2.sumtype)) ty

left join

(select prc_code,cat_prc_name from m_e_cat_prc where org_no like concat({供电单位}, '%')) p on ty.prc_code=p.prc_code order by ty.sumtype

-- 文件名：线路台区电量-按县公司
SELECT

	o1.NAME AS 用户单位,

	( SELECT NAME FROM ac_org WHERE CODE = ( SELECT l.org_no FROM m_g_line l WHERE id = a.line_id ) ) 线路单位,

-- 	a.line_id,

	gl2.line_no AS 线路编号,

	gl1.line_name AS 线路名称,

-- 	a.tg_id,

	gt2.tg_no AS 台区编号,

	gt1.tg_name AS 台区名称,

	(

	SELECT NAME

	FROM

		m_p_code

	WHERE

		code_type = 'pubPrivFlag'

	AND

	VALUE

		= ( SELECT g.pub_priv_flag FROM m_g_tg g WHERE id = a.tg_id )

	) 专公变标识,

	ifnull(sum( d.settle_apq ) ,0) 售电量

FROM

	m_e_mp_para_snap_arc a

	LEFT JOIN m_e_mp_pq_arc d ON a.id = d.mp_para_snap_id

	AND a.ym = d.ym

	LEFT JOIN m_e_cons_snap_arc c ON c.ym = a.ym

	AND c.id = a.calc_id


LEFT JOIN ac_org o1 ON CODE = c.org_no
LEFT JOIN m_g_line gl2 ON id = a.line_id
LEFT JOIN m_g_line gl1 ON id = a.line_id
LEFT JOIN m_g_tg gt2 ON id = a.tg_id
LEFT JOIN m_g_tg gt1 ON id = a.tg_id
WHERE 1=1

 and c.org_No LIKE concat({县公司单位},'%')

  and a.ym={电费年月}

group by a.line_id,a.tg_id

-- 文件名：线损查询
SELECT

	yy.线路编号,

	yy.线路名称,

	yy.电压等级,

	yy.所属变电站,

	yy.关口表代码,

	yy.倍率,

	yy.上月止数正向,

	yy.本月止数正向,

	yy.追退电量正向,

	yy.上月止数反向,

	yy.本月止数反向,

	yy.追退电量反向,

	yy.发电站上网电量,

	yy.电量正向总,

	yy.电量反向总,

	(供电 +追退电量正向) 供电量,

	(	台区用户电量合计1 +专变用电量1 ) 售电量,

	yy.公变变压器个数,

	yy.公变容量合计,

	yy.总表电量,

  yy.台区用户电量合计1 台区用户电量合计,

	yy.专变变压器个数,

	yy.专变变压器容量合计,

  yy.专变用电量1 专变用电量

FROM

	(

	SELECT

		gg.line_no 线路编号,

		gg.line_name 线路名称,

		( SELECT NAME FROM m_p_code p WHERE code_type = 'psVoltCode' AND VALUE = gg.volt_code ) 电压等级,

		(

		SELECT

			sub.subs_name

		FROM

			m_g_subs sub,

			m_g_subs_line_rela resub

		WHERE

			resub.line_id = gg.idd

			AND resub.subs_id = sub.id

		) 所属变电站,

		'' 关口表代码,

		ifnull( ry.t_factor, 0 ) 倍率,

		ifnull( ry.last_mr_num, 0 ) 上月止数正向,

		ifnull( ry.this_read, 0 ) 本月止数正向,

		ifnull(

			(

			SELECT

				sum( adj.adj_pq )

			FROM

				m_g_chkunit_comp comp,

				m_g_pq_adj adj

			WHERE

				comp.obj_id = gg.idd

				AND adj.chkunit_id = comp.chkunit_id

				AND adj.adj_code = '01'

			),

			0

		) 追退电量正向,

		ifnull( rw.last_mr_num, 0 ) 上月止数反向,

		ifnull( rw.this_read, 0 ) 本月止数反向,

		0 追退电量反向,

		0 发电站上网电量,

		ifnull( ry.THIS_READ_PQ, 0 ) 电量正向总,

		ifnull( rw.this_read_pq, 0 ) 电量反向总,

		ifnull( ( ry.THIS_READ_PQ - rw.this_read_pq ), 0 ) 供电,

		0 售电,

		(

		SELECT

			ifnull( count( 1 ), 0 ) trannum -- 变压器个数



		FROM

			m_g_line_tg_rela re,

			m_g_tran tran

		WHERE

			re.line_id = gg.idd

			AND tran.tg_id = re.tg_id

			AND tran.pub_priv_flag = '01' -- 公变变压器



			AND tran.chg_remark <> '04'

		) 公变变压器个数,

		(

		SELECT

			ifnull( sum( tran.plate_cap ), 0 ) plate_cap -- 变压器容量合计



		FROM

			m_g_line_tg_rela re,

			m_g_tran tran

		WHERE

			re.line_id = gg.idd

			AND tran.tg_id = re.tg_id

			AND tran.pub_priv_flag = '01' -- 公变变压器



			AND tran.chg_remark <> '04'

		) 公变容量合计,

		(

		SELECT

			ifnull( sum( this_read_pq ), 0 ) sumpqtg -- 所有公变台区表的抄见电量



		FROM

			m_g_line_tg_rela re,

			m_c_mp mptg,

			m_r_data_arc rtg

		WHERE

			re.line_id = gg.idd

			AND re.tg_id = mptg.tg_id

			AND rtg.mp_id = mptg.id

			AND rtg.read_type_code = '11'

			AND rtg.amt_ym = {电费年月}

			AND mptg.type_code = '03' -- 台区关口



			AND rtg.org_no LIKE {供电单位}

		) 总表电量,

 			(

			SELECT

				ifnull( sum( amt.t_settle_pq ), 0 )



				FROM

					m_e_mp_para_snap_arc mpyh , m_g_tg tgg,m_e_cons_prc_amt_arc amt

				WHERE

					mpyh.line_id = gg.idd and tgg.id = mpyh.tg_id AND tgg.pub_priv_flag = '01'

					AND mpyh.ym = {电费年月}

					AND mpyh.org_no LIKE {供电单位}  and amt.calc_id = mpyh.calc_id



		) 台区用户电量合计1,



		(

		SELECT

			ifnull( count( 1 ), 0 ) trannum -- 变压器个数



		FROM

			m_g_line_tg_rela re,

			m_g_tran tran

		WHERE

			re.line_id = gg.idd

			AND tran.tg_id = re.tg_id

			AND tran.pub_priv_flag = '02' -- 公变变压器



		) 专变变压器个数,

		(

		SELECT

			ifnull( sum( tran.plate_cap ), 0 ) plate_cap -- 变压器容量合计



		FROM

			m_g_line_tg_rela re,

			m_g_tran tran

		WHERE

			re.line_id = gg.idd

			AND tran.tg_id = re.tg_id

			AND tran.pub_priv_flag = '02' -- 公变变压器



		) 专变变压器容量合计,

			(

				select ifnull( sum( amt.t_settle_pq ), 0 )



				FROM

					m_e_mp_para_snap_arc mpyh , m_g_tg tgg,m_e_cons_prc_amt_arc amt

				WHERE

					mpyh.line_id = gg.idd and tgg.id = mpyh.tg_id AND tgg.pub_priv_flag = '02'

					AND mpyh.ym = {电费年月}

					AND mpyh.org_no LIKE {供电单位}  and amt.calc_id = mpyh.calc_id

		) 专变用电量1

	FROM

		(

		SELECT

			g.id idd,

			g.line_no,

			g.line_name,

			g.volt_code,

     mp.org_no,

			mp.id

		FROM

			m_g_line g

			LEFT JOIN m_c_mp mp ON mp.line_id = g.id

		WHERE

			mp.type_code = '02'

			AND mp.org_no LIKE {供电单位}

			AND g.RUN_STATUS_CODE = '01' and mp.org_no = g.org_no



		) gg

		LEFT JOIN m_r_data_arc ry ON ry.mp_id = gg.id

		AND ry.amt_ym = {电费年月} and ry.org_no = gg.org_no and gg.id = ry.mp_id

		AND ry.read_type_code = '11'

		LEFT JOIN m_r_data_arc rw ON rw.mp_id = gg.id

		AND rw.amt_ym = {电费年月} and rw.org_no = gg.org_no and gg.id = ry.mp_id

		AND rw.read_type_code = '41'

	) yy

ORDER BY

	线路编号

-- 文件名：线损情况统计_四分统计表(分区域)
select gs_name 县公司,org_name 供电单位,g_ppq 供电量,g_spq 售电量,g_ll_pq 线损电量,'12%' 考核值,round(g_llr,2)  线损率

from (

    select distinct po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

      from m_g_chkunit a

      join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

      join ac_org o on a.org_no=o.id

      join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

      where a.chkunit_type_code='04'

) t1

left join (

    select a.org_no,g_ppq ,g_spq ,g_ll_pq ,g_llr

    from m_g_ll_stat a

    join m_g_g_ll_stat b on a.id=b.stat_id

    where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

) xs on t1.org_no=xs.org_no

order by 1,2

-- 文件名：线损情况统计_四分统计表(分压)
select gs_name 县公司,volt_name 电压等级,l_ppq 合计供电量,l_spq 合计售电量,l_ll_pq 损失电量,(case t1.volt_code when 'AC00101' then '8%' when 'AC00351' then '5%' when 'AC01101' then '3%' when 'AC02201' then '1%' end) 考核值,round(tp_llr,2) 线损率

from (

      select distinct po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id,p.value volt_code,p.name volt_name

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

      from m_g_chkunit a

      join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

      join ac_org o on a.org_no=o.id

      join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

      join m_p_code p on b.obj_id=p.id

      where a.chkunit_type_code='03'

) t1

left join (

    select left(a.org_no,7) gs_id,b.volt_code,l_ppq ,l_spq ,l_ll_pq , tp_llr

    from m_g_ll_stat a

    join m_g_ll_stat_byvolt b on a.id=b.stat_id

    -- left join m_p_code p on p.code_type='psVoltCode' and p.value=volt_code

    where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

) xs on t1.gs_id=xs.gs_id and t1.volt_code=xs.volt_code

order by 1,2

-- 文件名：线损情况统计_四分统计表(分线路)
select 县公司,电压等级,count(distinct 线路标识) 总条数

,count((case when 电压等级='交流10kV' and ifnull(合计供电量,0)>0 and 线损率 >= 0 and 线损率<=8 then 线路标识

         when 电压等级='交流35kV' and ifnull(合计供电量,0)>0 and 线损率 >= 0 and 线损率<=5 then 线路标识

         when 电压等级='交流110kV' and ifnull(合计供电量,0)>0 and 线损率 >= 0 and 线损率<=3 then 线路标识

         when 电压等级='交流220kV' and ifnull(合计供电量,0)>0 and 线损率 >= 0 and 线损率<=1 then 线路标识

 end)) 正常条数

,count((case

         when 电压等级='交流10kV' and (ifnull(合计供电量,0)=0 or 线损率<0 or 线损率>8) then 线路标识

         when 电压等级='交流35kV' and (ifnull(合计供电量,0)=0 or 线损率<0 or 线损率>5) then 线路标识

         when 电压等级='交流110kV' and (ifnull(合计供电量,0)=0 or 线损率<0 or 线损率>3) then 线路标识

         when 电压等级='交流220kV' and (ifnull(合计供电量,0)=0 or 线损率<0 or 线损率>1) then 线路标识

 end)) 异常条数

 ,(case when 电压等级='交流10kV' then '8%' when 电压等级='交流35kV' then '5%' when 电压等级='交流110kV' then '3%' when 电压等级='交流220kV' then '1%' end) 考核值

from (

    -- 明细

    select gs_name 县公司,org_name 供电单位,volt_name 电压等级,t1.line_id 线路标识,t1.line_no 线路编码,t1.line_name 线路名称,t_ppq 合计供电量,t_spq 合计售电量,lpq 损失电量,(case volt_name when '交流10kV' then '8%' when '交流35kV' then '5%' when '交流110kV' then '3%' when '交流220kV' then '1%' end) 考核值,round(l_llr,2) 线损率

    from (

        select distinct po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id line_id,l.line_no,l.line_name,p.name volt_name

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

        from m_g_chkunit a

        join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

        join m_g_line l on b.obj_id=l.id and l.run_status_code='01'

        join ac_org o on a.org_no=o.id

        join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

        left join m_p_code p on p.code_type='psVoltCode' and p.value=l.volt_code

        where a.chkunit_type_code='01'

    ) t1

    left join (

      select a.org_no,l.id line_id,t_ppq ,t_spq ,lpq ,l_llr

      from m_g_ll_stat a

      join (

        select stat_id,chkunit_org_no,line_id,line_no,line_name,t_ppq,t_spq,lpq,l_llr from m_g_llr_cmpl

        union all

        select stat_id,chkunit_org_no,line_id,line_no,line_name,t_ppq,t_spq,lpq,l_llr from m_g_llr_cmpl_highvolt

      ) b on a.id=b.stat_id

      join m_g_chkunit_comp c on b.line_id=c.chkunit_id and c.obj_type_code='01'

      join m_g_line l on c.obj_id=l.id and b.line_no=l.line_no

      left join m_p_code p on p.code_type='psVoltCode' and p.value=l.volt_code

      where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

    ) xs on t1.org_no=xs.org_no and t1.line_id=xs.line_id

    order by 1,2,3

) x group by 县公司,电压等级

order by 1,6 desc

-- 文件名：线损情况统计_四分统计表(分线路)_线路明细
select gs_name 县公司,org_name 供电单位,volt_name 电压等级,t1.line_id 线路标识,t1.line_no 线路编码,t1.line_name 线路名称,t_ppq 合计供电量,t_spq 合计售电量,lpq 损失电量,(case volt_name when '交流10kV' then '8%' when '交流35kV' then '5%' when '交流110kV' then '3%' when '交流220kV' then '1%' end) 考核值,round(l_llr,2) 线损率

    from (

        select distinct po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id line_id,l.line_no,l.line_name,p.name volt_name

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

        from m_g_chkunit a

        join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

        join m_g_line l on b.obj_id=l.id and l.run_status_code='01'

        join ac_org o on a.org_no=o.id

        join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

        left join m_p_code p on p.code_type='psVoltCode' and p.value=l.volt_code

        where a.chkunit_type_code='01'

    ) t1

    left join (

      select a.org_no,l.id line_id,t_ppq ,t_spq ,lpq ,l_llr

      from m_g_ll_stat a

      join (

        select stat_id,chkunit_org_no,line_id,line_no,line_name,t_ppq,t_spq,lpq,l_llr from m_g_llr_cmpl

        union all

        select stat_id,chkunit_org_no,line_id,line_no,line_name,t_ppq,t_spq,lpq,l_llr from m_g_llr_cmpl_highvolt

      ) b on a.id=b.stat_id

      join m_g_chkunit_comp c on b.line_id=c.chkunit_id and c.obj_type_code='01'

      join m_g_line l on c.obj_id=l.id and b.line_no=l.line_no

      left join m_p_code p on p.code_type='psVoltCode' and p.value=l.volt_code

      where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

    ) xs on t1.org_no=xs.org_no and t1.line_id=xs.line_id

    order by 1,2,3

-- 文件名：线损情况统计_四分统计表(分台区)
select 县公司,count(distinct 台区标识) 台区总数

,count((case when ifnull(合计供电量,0)>0 and 线损率>=0 and 线损率<=12 then 台区标识 end)) 正常台区数

,count((case when ifnull(合计供电量,0)=0 or 线损率<0 or 线损率>12 then 台区标识 end)) 异常台区数

,concat(round(count((case when ifnull(合计供电量,0)>0 and 线损率>=0 and 线损率<=12 then 台区标识 end))/count(distinct 台区标识)*100,2),'%') 合格率

,'12%' 考核值

from (

    -- 明细

       select gs_name 县公司,org_name 供电单位,t1.tg_id 台区标识,t1.tg_no 台区编码,t1.tg_name 台区名称,t_ppq 合计供电量,t_spq 合计售电量,lpq 损失电量,'12%' 考核值,round(l_llr,2) 线损率

    from (

        select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id tg_id,tg_no,replace(replace(replace(replace(tg.tg_name,char(13),''),char(10),''),char(9),''),char(32),'') tg_name,p1.name pub_priv_flag

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

        from m_g_chkunit a

        join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

        join m_g_tg tg on b.obj_id=tg.id and tg.run_status_code='01'

        join ac_org o on a.org_no=o.id

        join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

        left join m_p_code p1 on p1.code_type='pubPrivFlag' and p1.`value`=tg.pub_priv_flag

        where a.chkunit_type_code='02'

    ) t1

    left join (

        select a.org_no,tg.id tg_id,t_ppq ,t_spq ,lpq ,l_llr

        from m_g_ll_stat a

        join m_g_tg_ll_det b on a.id=b.stat_id

        join m_g_chkunit_comp c on b.tg_id=c.chkunit_id and c.obj_type_code='02'

        join m_g_tg tg on c.obj_id=tg.id and b.tg_no=tg.tg_no

        where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

    ) xs on t1.org_no=xs.org_no and t1.tg_id=xs.tg_id

    order by 1,2

) x group by 县公司

ORDER BY 1

-- 文件名：线损情况统计_四分统计表(分台区)_台区明细
select gs_name 县公司,org_name 供电单位,t1.tg_id 台区标识,t1.tg_no 台区编码,t1.tg_name 台区名称,t_ppq 合计供电量,t_spq 合计售电量,lpq 损失电量,'12%' 考核值,round(l_llr,2) 线损率

    from (

        select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id tg_id,tg_no,replace(replace(replace(replace(tg.tg_name,char(13),''),char(10),''),char(9),''),char(32),'') tg_name,p1.name pub_priv_flag

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

        from m_g_chkunit a

        join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

        join m_g_tg tg on b.obj_id=tg.id and tg.run_status_code='01'

        join ac_org o on a.org_no=o.id

        join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

        left join m_p_code p1 on p1.code_type='pubPrivFlag' and p1.`value`=tg.pub_priv_flag

        where a.chkunit_type_code='02'

    ) t1

    left join (

        select a.org_no,tg.id tg_id,t_ppq ,t_spq ,lpq ,l_llr

        from m_g_ll_stat a

        join m_g_tg_ll_det b on a.id=b.stat_id

        join m_g_chkunit_comp c on b.tg_id=c.chkunit_id and c.obj_type_code='02'

        join m_g_tg tg on c.obj_id=tg.id and b.tg_no=tg.tg_no

        where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

    ) xs on t1.org_no=xs.org_no and t1.tg_id=xs.tg_id

    order by 1,2

-- 文件名：线损情况统计_考核单元完整性(分区)
select 公司编码,公司名称

	,count(distinct 单位编码) 供电所档案数

	,count(distinct 考核单元标识) 考核单元数

	,count(case when 供电量组成='有' then 1 end) 供电量组成

	,count(case when 售电量组成='有' then 1 end) 售电量组成

	,count(case when 配置情况='异常' then 1 end) `供、售组成不完整`

from (

    -- 明细

       select t1.gs_id 公司编码,t1.gs_name 公司名称,t1.org_no 单位编码,t1.org_name 单位名称

      ,(select count(1) from m_g_chkunit x join m_g_chkunit_comp y on x.id=y.chkunit_id and x.chkunit_type_code=y.obj_type_code where x.chkunit_type_code='04' and left(x.org_no,7)=t1.gs_id and y.obj_id=t1.org_no) 相关考核单元数量

      ,t2.chkunit_id 考核单元标识,replace(replace(replace(replace(t2.chkunit_name,char(13),''),char(10),''),char(9),''),char(32),'')

     考核单元名称,t2.gdl_comp 供电量组成数,t2.sdl_comp 售电量组成数

      ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 then '有' else '无' end) 供电量组成

      ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.sdl_comp,0)>0 then '有' else '无' end) 售电量组成

      ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 and ifnull(t2.sdl_comp,0)>0 then '正常' else '异常' end) 配置情况

    from (

      select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name

      from ac_org o

      join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

      where o.type='0'

    ) t1

    left join (

      select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

      from m_g_chkunit a

      join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

      join ac_org o on a.org_no=o.id

      join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

      where a.chkunit_type_code='04'

    ) t2 on t1.gs_id=t2.gs_id and t1.org_no=t2.obj_id

    order by 1,3

) ut

group by 公司编码,公司名称

order by 1,2

-- 文件名：线损情况统计_考核单元完整性(分区)_明细
select t1.gs_id 公司编码,t1.gs_name 公司名称,t1.org_no 单位编码,t1.org_name 单位名称

      ,(select count(1) from m_g_chkunit x join m_g_chkunit_comp y on x.id=y.chkunit_id and x.chkunit_type_code=y.obj_type_code where x.chkunit_type_code='04' and left(x.org_no,7)=t1.gs_id and y.obj_id=t1.org_no) 相关考核单元数量

      ,t2.chkunit_id 考核单元标识,replace(replace(replace(replace(t2.chkunit_name,char(13),''),char(10),''),char(9),''),char(32),'')

     考核单元名称,t2.gdl_comp 供电量组成数,t2.sdl_comp 售电量组成数

      ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 then '有' else '无' end) 供电量组成

      ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.sdl_comp,0)>0 then '有' else '无' end) 售电量组成

      ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 and ifnull(t2.sdl_comp,0)>0 then '正常' else '异常' end) 配置情况

    from (

      select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name

      from ac_org o

      join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

      where o.type='0'

    ) t1

    left join (

      select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

      from m_g_chkunit a

      join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

      join ac_org o on a.org_no=o.id

      join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

      where a.chkunit_type_code='04'

    ) t2 on t1.gs_id=t2.gs_id and t1.org_no=t2.obj_id

    order by 1,3

-- 文件名：线损情况统计_考核单元完整性(分电压)
select 公司编码,公司名称

	,count(distinct 电压等级代码) 电压等级档案数

	,count(考核单元标识) 考核单元数

	,count(case when 供电量组成='有' then 1 end) 供电量组成

	,count(case when 售电量组成='有' then 1 end) 售电量组成

	,count(case when 配置情况='异常' then 1 end) `供、售组成不完整`

from (

    -- 明细

    select t1.gs_id 公司编码,t1.gs_name 公司名称,t2.org_no 单位编码,t2.org_name 单位名称,t1.volt_code 电压等级代码,t1.volt_name 电压等级

      ,(select count(1) from m_g_chkunit x join m_g_chkunit_comp y on x.id=y.chkunit_id and x.chkunit_type_code=y.obj_type_code where x.chkunit_type_code='03' and left(x.org_no,7)=t1.gs_id and y.obj_id=t1.volt_id) 相关考核单元数量

      ,t2.chkunit_id 考核单元标识,replace(replace(replace(replace(t2.chkunit_name,char(13),''),char(10),''),char(9),''),char(32),'') 考核单元名称,t2.gdl_comp 供电量组成数,t2.sdl_comp 售电量组成数

      ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 then '有' else '无' end) 供电量组成

      ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.sdl_comp,0)>0 then '有' else '无' end) 售电量组成

      ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 and ifnull(t2.sdl_comp,0)>0 then '正常' else '异常' end) 配置情况

    from (

      select po.id gs_id,po.name gs_name,volt_code,volt_name,volt_id

      from ac_org po

      ,(select 'AC00101' volt_code,'交流10kV' volt_name,96964149010435 volt_id union all

        select 'AC00351' volt_code,'交流35kV' volt_name,96964149010439 volt_id union all

        select 'AC01101' volt_code,'交流110kV' volt_name,96964149010442 volt_id union all

        select 'AC02201' volt_code,'交流220kV' volt_name,96964149010444 volt_id

      ) dydj

      where  length(po.id)=7 and po.id=left({组织},7)

      order by 1

    ) t1

    left join (

      select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

      from m_g_chkunit a

      join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

      join ac_org o on a.org_no=o.id

      join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

      where a.chkunit_type_code='03'

    ) t2 on t1.gs_id=t2.gs_id and t1.volt_id=t2.obj_id

    order by 1,3,5

) ut

group by 公司编码,公司名称

-- 文件名：线损情况统计_考核单元完整性(分电压)_明细
select t1.gs_id 公司编码,t1.gs_name 公司名称,t2.org_no 单位编码,t2.org_name 单位名称,t1.volt_code 电压等级代码,t1.volt_name 电压等级

      ,(select count(1) from m_g_chkunit x join m_g_chkunit_comp y on x.id=y.chkunit_id and x.chkunit_type_code=y.obj_type_code where x.chkunit_type_code='03' and left(x.org_no,7)=t1.gs_id and y.obj_id=t1.volt_id) 相关考核单元数量

      ,t2.chkunit_id 考核单元标识,replace(replace(replace(replace(t2.chkunit_name,char(13),''),char(10),''),char(9),''),char(32),'') 考核单元名称,t2.gdl_comp 供电量组成数,t2.sdl_comp 售电量组成数

      ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 then '有' else '无' end) 供电量组成

      ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.sdl_comp,0)>0 then '有' else '无' end) 售电量组成

      ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 and ifnull(t2.sdl_comp,0)>0 then '正常' else '异常' end) 配置情况

    from (

      select po.id gs_id,po.name gs_name,volt_code,volt_name,volt_id

      from ac_org po

      ,(select 'AC00101' volt_code,'交流10kV' volt_name,96964149010435 volt_id union all

        select 'AC00351' volt_code,'交流35kV' volt_name,96964149010439 volt_id union all

        select 'AC01101' volt_code,'交流110kV' volt_name,96964149010442 volt_id union all

        select 'AC02201' volt_code,'交流220kV' volt_name,96964149010444 volt_id

      ) dydj

      where  length(po.id)=7 and po.id=left({组织},7)

      order by 1

    ) t1

    left join (

      select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

      from m_g_chkunit a

      join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

      join ac_org o on a.org_no=o.id

      join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

      where a.chkunit_type_code='03'

    ) t2 on t1.gs_id=t2.gs_id and t1.volt_id=t2.obj_id

    order by 1,3,5

-- 文件名：线损情况统计_考核单元完整性(线路类)
select 公司编码,公司名称,电压等级

	,count(distinct 线路标识) 线路档案数

	,count(考核单元标识) 考核单元数

	,count(case when 供电量组成='有' then 1 end) 供电量组成

	,count(case when 售电量组成='有' then 1 end) 售电量组成

	,count(case when 配置情况='异常' then 1 end) `供、售组成不完整`

from (

      -- 明细

      select t1.gs_id 公司编码,t1.gs_name 公司名称,t1.org_no 单位编码,t1.org_name 单位名称,t1.volt_name 电压等级

        ,t1.line_id 线路标识,t1.line_no 线路编码,replace(replace(replace(replace(t1.line_name,char(13),''),char(10),''),char(9),''),char(32),'') 线路名称

        ,(select count(1) from m_g_chkunit x join m_g_chkunit_comp y on x.id=y.chkunit_id and x.chkunit_type_code=y.obj_type_code where x.chkunit_type_code='01' and left(x.org_no,7)=t1.gs_id and y.obj_id=t1.line_id) 相关考核单元数量

        ,t2.chkunit_id 考核单元标识,replace(replace(replace(replace(t2.chkunit_name,char(13),''),char(10),''),char(9),''),char(32),'') 考核单元名称,t2.gdl_comp 供电量组成数,t2.sdl_comp 售电量组成数

        ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 then '有' else '无' end) 供电量组成

        ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.sdl_comp,0)>0 then '有' else '无' end) 售电量组成

        ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 and ifnull(t2.sdl_comp,0)>0 then '正常' else '异常' end) 配置情况

      from (

        select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id line_id,a.line_no,a.line_name,p1.`name` volt_name

        from m_g_line a

        join ac_org o on a.org_no=o.id

        join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

        left join m_p_code p1 on p1.code_type='psVoltCode' and p1.`value`=a.volt_code

        where a.run_status_code='01'

          and ifnull(a.GENERATRIX_FLAG,'')<>'1'

      ) t1

      left join (

        select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

        from m_g_chkunit a

        join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

        join ac_org o on a.org_no=o.id

        join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

        where a.chkunit_type_code='01'

      ) t2 on t1.gs_id=t2.gs_id and t1.line_id=t2.obj_id

      order by 1,3,5

) ut

group by 公司编码,公司名称,电压等级

order by 1,3

-- 文件名：线损情况统计_考核单元完整性(线路类)_明细
select t1.gs_id 公司编码,t1.gs_name 公司名称,t1.org_no 单位编码,t1.org_name 单位名称,t1.volt_name 电压等级

        ,t1.line_id 线路标识,t1.line_no 线路编码,replace(replace(replace(replace(t1.line_name,char(13),''),char(10),''),char(9),''),char(32),'') 线路名称

        ,(select count(1) from m_g_chkunit x join m_g_chkunit_comp y on x.id=y.chkunit_id and x.chkunit_type_code=y.obj_type_code where x.chkunit_type_code='01' and left(x.org_no,7)=t1.gs_id and y.obj_id=t1.line_id) 相关考核单元数量

        ,t2.chkunit_id 考核单元标识,replace(replace(replace(replace(t2.chkunit_name,char(13),''),char(10),''),char(9),''),char(32),'') 考核单元名称,t2.gdl_comp 供电量组成数,t2.sdl_comp 售电量组成数

        ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 then '有' else '无' end) 供电量组成

        ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.sdl_comp,0)>0 then '有' else '无' end) 售电量组成

        ,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 and ifnull(t2.sdl_comp,0)>0 then '正常' else '异常' end) 配置情况

      from (

        select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id line_id,a.line_no,a.line_name,p1.`name` volt_name

        from m_g_line a

        join ac_org o on a.org_no=o.id

        join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

        left join m_p_code p1 on p1.code_type='psVoltCode' and p1.`value`=a.volt_code

        where a.run_status_code='01'

          and ifnull(a.GENERATRIX_FLAG,'')<>'1'

      ) t1

      left join (

        select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

        from m_g_chkunit a

        join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

        join ac_org o on a.org_no=o.id

        join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

        where a.chkunit_type_code='01'

      ) t2 on t1.gs_id=t2.gs_id and t1.line_id=t2.obj_id

      order by 1,3,5

-- 文件名：线损情况统计_考核单元完整性(台区类)
select 公司编码,公司名称

	,count(distinct 台区标识) 台区档案数

	,count(考核单元标识) 考核单元数

	,count(case when 供电量组成='有' then 1 end) 供电量组成

	,count(case when 售电量组成='有' then 1 end) 售电量组成

	,count(case when 配置情况='异常' then 1 end) `供、售组成不完整`

from (

  -- 明细

	select t1.gs_id 公司编码,t1.gs_name 公司名称,t1.org_no 单位编码,t1.org_name 单位名称

		,t1.tg_id 台区标识,t1.tg_no 台区编码,replace(replace(replace(replace(t1.tg_name,char(13),''),char(10),''),char(9),''),char(32),'') 台区名称,t1.pub_priv_flag 公专变标识

		,(select count(1) from m_g_chkunit x join m_g_chkunit_comp y on x.id=y.chkunit_id and x.chkunit_type_code=y.obj_type_code where x.chkunit_type_code='02' and left(x.org_no,7)=t1.gs_id and y.obj_id=t1.tg_id) 相关考核单元数量

		,t2.chkunit_id 考核单元标识,replace(replace(replace(replace(t2.chkunit_name,char(13),''),char(10),''),char(9),''),char(32),'') 考核单元名称,t2.gdl_comp 供电量组成数,t2.sdl_comp 售电量组成数

		,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 then '有' else '无' end) 供电量组成

		,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.sdl_comp,0)>0 then '有' else '无' end) 售电量组成

		,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 and ifnull(t2.sdl_comp,0)>0 then '正常' else '异常' end) 配置情况

	from (

		select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id tg_id,a.tg_no,replace(replace(replace(replace(a.tg_name,char(13),''),char(10),''),char(9),''),char(32),'') tg_name,p1.`name` pub_priv_flag

		from m_g_tg a

		join ac_org o on a.org_no=o.id

	  join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

		left join m_p_code p1 on p1.code_type='pubPrivFlag' and p1.`value`=a.pub_priv_flag

		where a.run_status_code='01' and a.pub_priv_flag='01'

	) t1

	left join (

		select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id

			,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

			,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

		from m_g_chkunit a

		join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

		join ac_org o on a.org_no=o.id

		join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

		where a.chkunit_type_code='02'

	) t2 on t1.gs_id=t2.gs_id and t1.tg_id=t2.obj_id

  order by 1,3

) ut

group by 公司编码,公司名称

order by 1

-- 文件名：线损情况统计_考核单元完整性(台区类)_明细
select t1.gs_id 公司编码,t1.gs_name 公司名称,t1.org_no 单位编码,t1.org_name 单位名称

		,t1.tg_id 台区标识,t1.tg_no 台区编码,replace(replace(replace(replace(t1.tg_name,char(13),''),char(10),''),char(9),''),char(32),'') 台区名称,t1.pub_priv_flag 公专变标识

		,(select count(1) from m_g_chkunit x join m_g_chkunit_comp y on x.id=y.chkunit_id and x.chkunit_type_code=y.obj_type_code where x.chkunit_type_code='02' and left(x.org_no,7)=t1.gs_id and y.obj_id=t1.tg_id) 相关考核单元数量

		,t2.chkunit_id 考核单元标识,replace(replace(replace(replace(t2.chkunit_name,char(13),''),char(10),''),char(9),''),char(32),'') 考核单元名称,t2.gdl_comp 供电量组成数,t2.sdl_comp 售电量组成数

		,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 then '有' else '无' end) 供电量组成

		,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.sdl_comp,0)>0 then '有' else '无' end) 售电量组成

		,(case when t2.chkunit_id is null then '缺失' when ifnull(t2.gdl_comp,0)>0 and ifnull(t2.sdl_comp,0)>0 then '正常' else '异常' end) 配置情况

	from (

		select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id tg_id,a.tg_no,replace(replace(replace(replace(a.tg_name,char(13),''),char(10),''),char(9),''),char(32),'') tg_name,p1.`name` pub_priv_flag

		from m_g_tg a

		join ac_org o on a.org_no=o.id

	  join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

		left join m_p_code p1 on p1.code_type='pubPrivFlag' and p1.`value`=a.pub_priv_flag

		where a.run_status_code='01' and a.pub_priv_flag='01'

	) t1

	left join (

		select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id

			,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

			,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

		from m_g_chkunit a

		join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

		join ac_org o on a.org_no=o.id

		join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

		where a.chkunit_type_code='02'

	) t2 on t1.gs_id=t2.gs_id and t1.tg_id=t2.obj_id

  order by 1,3

-- 文件名：线损情况统计_线路无关口表
select po.id 公司编码,po.`name` 公司名称,o.id 单位编码,o.`name` 单位名称,a.id 线路标识,a.line_no 线路编码,replace(replace(replace(replace(a.line_name,char(13),''),char(10),''),char(9),''),char(32),'') 线路名称,p1.`name` 电压等级

	from m_g_line a

	join ac_org o on a.org_no=o.id

	join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

	left join m_p_code p1 on p1.code_type='psVoltCode' and p1.`value`=a.volt_code

	where a.run_status_code='01' and ifnull(a.GENERATRIX_FLAG,'')<>'1'

  and not exists (select 1 from m_c_mp b where a.id=b.line_id and b.status_code in('01','02') and b.type_code='02')

order by 1,3

-- 文件名：线损情况统计_台区无关口表
select po.id 公司编码,po.`name` 公司名称,o.id 单位编码,o.`name` 单位名称,a.id 台区标识,a.tg_no 台区编码,replace(replace(replace(replace(a.tg_name,char(13),''),char(10),''),char(9),''),char(32),'') 台区名称,p1.`name` 公专变标识

		from m_g_tg a

		join ac_org o on a.org_no=o.id

	  join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id=left({组织},7)

		left join m_p_code p1 on p1.code_type='pubPrivFlag' and p1.`value`=a.pub_priv_flag

		where a.run_status_code='01' and a.pub_priv_flag='01'

    and not exists (select 1 from m_c_mp b where a.id=b.tg_id and b.status_code in('01','02') and b.type_code='03')

order by 1,3

-- 文件名：线损情况统计_四分异常(总表)
select xo.short_name 公司名称

,台区总数,台区异常数量,`台区异常其中：正负30%以上`,`台区异常其中：其他`,台区异常占比,台区未配置考核单元数量

,线路总数,线路异常数量,`线路异常其中：正负30%以上`,`线路异常其中：其他`,线路异常占比,线路未配置考核单元数量

,供电所总数,供电所异常数量,`供电所异常其中：正负30%以上`,`供电所异常其中：其他`,供电所异常占比,供电所未配置考核单元数量

,分压总数,分压异常数量,`分压异常其中：正负30%以上`,`分压异常其中：其他`,分压异常占比,分压未配置考核单元数量

from ac_org xo

-- 分台区

left join (

    select gs_id,count(distinct tg_id) 台区总数

    ,count((case when ifnull(t_ppq,0)>0 and l_llr>=0 and l_llr<=12 then tg_id end)) 正常台区数

    ,count((case when ifnull(t_ppq,0)=0 or l_llr<0 or l_llr>12 then tg_id end)) 台区异常数量

    ,count((case when l_llr<=-30 or l_llr>=30 then tg_id end)) `台区异常其中：正负30%以上`

    ,count((case when ifnull(t_ppq,0)=0 or (l_llr>-30 and l_llr<0) or (l_llr>12 and l_llr<30) then tg_id end)) `台区异常其中：其他`

    ,concat(round(count((case when ifnull(t_ppq,0)=0 or l_llr<0 or l_llr>12 then tg_id end))/count(distinct tg_id)*100,2),'%') 台区异常占比

    from (

          select gs_id,t1.tg_id,t_ppq ,t_spq ,lpq ,l_llr

          from (

              select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id tg_id,tg_no,replace(replace(replace(replace(tg.tg_name,char(13),''),char(10),''),char(9),''),char(32),'') tg_name,p1.name pub_priv_flag

            ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

            ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

              from m_g_chkunit a

              join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

              join m_g_tg tg on b.obj_id=tg.id and tg.run_status_code='01'

              join ac_org o on a.org_no=o.id

              join ac_org po on left(o.id,7)=po.id and length(po.id)=7 #and po.id like concat({组织},'%')

              left join m_p_code p1 on p1.code_type='pubPrivFlag' and p1.`value`=tg.pub_priv_flag

              where a.chkunit_type_code='02'

        ) t1

        left join (

            select a.org_no,tg.id tg_id,t_ppq ,t_spq ,lpq ,l_llr

            from m_g_ll_stat a

            join m_g_tg_ll_det b on a.id=b.stat_id

            join m_g_chkunit_comp c on b.tg_id=c.chkunit_id and c.obj_type_code='02'

            join m_g_tg tg on c.obj_id=tg.id and b.tg_no=tg.tg_no

            where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

        ) xs on t1.org_no=xs.org_no and t1.tg_id=xs.tg_id

     ) x group by gs_id

) tg_xs on xo.id=tg_xs.gs_id

left join (

	select po.id gs_id,ifnull(count(a.id),0) 台区未配置考核单元数量

		from m_g_tg a

    join ac_org o on a.org_no=o.id

    join ac_org po on left(o.id,7)=po.id and length(po.id)=7 #and po.id like concat({组织},'%')

		where a.run_status_code='01' and a.pub_priv_flag='01' and not exists (select 1 from m_g_chkunit a1 , m_g_chkunit_comp b1 where a1.id=b1.chkunit_id and a1.chkunit_type_code=b1.obj_type_code and a1.chkunit_type_code='02' and b1.obj_id=a.id)

    group by po.id

) tg_kh on xo.id=tg_kh.gs_id

-- 分线路

left join (

  select gs_id,线路总数,线路正常数量,线路异常数量,`线路异常其中：正负30%以上`,(线路异常数量-`线路异常其中：正负30%以上`) `线路异常其中：其他`

  ,concat(round(线路异常数量/线路总数*100,2),'%') 线路异常占比

   from (

      select gs_id,count(distinct line_id) 线路总数

        ,count((case when volt_name='交流10kV' and ifnull(t_ppq,0)>0 and l_llr >= 0 and l_llr<=8 then line_id

         when volt_name='交流35kV' and ifnull(t_ppq,0)>0 and l_llr >= 0 and l_llr<=5 then line_id

         when volt_name='交流110kV' and ifnull(t_ppq,0)>0 and l_llr >= 0 and l_llr<=3 then line_id

         when volt_name='交流220kV' and ifnull(t_ppq,0)>0 and l_llr >= 0 and l_llr<=1 then line_id

         end)) 线路正常数量

        ,count((case when volt_name='交流10kV' and (ifnull(t_ppq,0)=0 or l_llr<0 or l_llr>8) then line_id

         when volt_name='交流35kV' and (ifnull(t_ppq,0)=0 or l_llr<0 or l_llr>5) then line_id

         when volt_name='交流110kV' and (ifnull(t_ppq,0)=0 or l_llr<0 or l_llr>3) then line_id

         when volt_name='交流220kV' and (ifnull(t_ppq,0)=0 or l_llr<0 or l_llr>1) then line_id

         end)) 线路异常数量

        ,count((case when l_llr<=-30 or l_llr>=30 then line_id end)) `线路异常其中：正负30%以上`

      from (

        select gs_id,volt_name ,t1.line_id ,t_ppq ,t_spq ,lpq ,l_llr

        from (

            select distinct po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id line_id,l.line_no,l.line_name,p.name volt_name

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

            from m_g_chkunit a

            join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

            join m_g_line l on b.obj_id=l.id and l.run_status_code='01'

            join ac_org o on a.org_no=o.id

            join ac_org po on left(o.id,7)=po.id and length(po.id)=7 #and po.id like concat({组织},'%')

            left join m_p_code p on p.code_type='psVoltCode' and p.value=l.volt_code

            where a.chkunit_type_code='01'

        ) t1

        left join (

            select a.org_no,l.id line_id,t_ppq ,t_spq ,lpq ,l_llr

            from m_g_ll_stat a

            join (

              select stat_id,chkunit_org_no,line_id,line_no,line_name,t_ppq,t_spq,lpq,l_llr from m_g_llr_cmpl

              union all

              select stat_id,chkunit_org_no,line_id,line_no,line_name,t_ppq,t_spq,lpq,l_llr from m_g_llr_cmpl_highvolt

            ) b on a.id=b.stat_id

            join m_g_chkunit_comp c on b.line_id=c.chkunit_id and c.obj_type_code='01'

            join m_g_line l on c.obj_id=l.id and b.line_no=l.line_no

            left join m_p_code p on p.code_type='psVoltCode' and p.value=l.volt_code

            where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

        ) xs on t1.org_no=xs.org_no and t1.line_id=xs.line_id

      ) xx group by gs_id

    ) x

) line_xs on xo.id=line_xs.gs_id

left join (

	select po.id gs_id,ifnull(count(a.id),0) 线路未配置考核单元数量

		from m_g_line a

    join ac_org o on a.org_no=o.id

    join ac_org po on left(o.id,7)=po.id and length(po.id)=7 #and po.id like concat({组织},'%')

		where a.run_status_code='01' and not exists (select 1 from m_g_chkunit a1 , m_g_chkunit_comp b1 where a1.id=b1.chkunit_id and a1.chkunit_type_code=b1.obj_type_code and a1.chkunit_type_code='01' and b1.obj_id=a.id)

    group by po.id

) line_kh on xo.id=line_kh.gs_id

-- 分区域

left join (

    select gs_id,count(distinct t1.org_no) 供电所总数

    ,count((case when ifnull(g_ppq,0)>0 and g_llr>=0 and g_llr<=12 then t1.org_no end)) 正常供电所数

    ,count((case when ifnull(g_ppq,0)=0 or g_llr<0 or g_llr>12 then t1.org_no end)) 供电所异常数量

    ,count((case when g_llr<=-30 or g_llr>=30 then t1.org_no end)) `供电所异常其中：正负30%以上`

    ,count((case when ifnull(g_ppq,0)=0 or (g_llr>-30 and g_llr<0) or (g_llr>12 and g_llr<30) then t1.org_no end)) `供电所异常其中：其他`

    ,concat(round(count((case when ifnull(g_ppq,0)=0 or g_llr<0 or g_llr>12 then t1.org_no end))/count(distinct t1.org_no)*100,2),'%') 供电所异常占比

    from (

        select distinct po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

        from m_g_chkunit a

        join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

        join ac_org o on a.org_no=o.id

        join ac_org po on left(o.id,7)=po.id and length(po.id)=7 #and po.id like concat({组织},'%')

        where a.chkunit_type_code='04'

    ) t1

    left join (

        select a.org_no,g_ppq ,g_spq ,g_ll_pq ,g_llr

        from m_g_ll_stat a

        join m_g_g_ll_stat b on a.id=b.stat_id

        where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

    ) xs on t1.org_no=xs.org_no

    group by gs_id

) gds_xs on xo.id=gds_xs.gs_id

left join (

    select po.id gs_id,ifnull(count(o.id),0) 供电所未配置考核单元数量

		from ac_org o

    join ac_org po on left(o.id,7)=po.id and length(po.id)=7 #and po.id like concat({组织},'%')

		where o.type='0' and not exists (select 1 from m_g_chkunit a1 , m_g_chkunit_comp b1 where a1.id=b1.chkunit_id and a1.chkunit_type_code=b1.obj_type_code and a1.chkunit_type_code='04' and b1.obj_id=o.id)

    group by po.id

) gds_kh on xo.id=gds_kh.gs_id

-- 分压

left join (

    select gs_id,分压总数,分压正常数量,分压异常数量,`分压异常其中：正负30%以上`,(分压异常数量-`分压异常其中：正负30%以上`) `分压异常其中：其他`

  ,concat(round(分压异常数量/分压总数*100,2),'%') 分压异常占比

   from (

       select gs_id,count(distinct t1.volt_code) 分压总数

      ,count((case when volt_name='交流10kV' and ifnull(l_ppq,0)>0 and tp_llr >= 0 and tp_llr<=8 then t1.volt_code

           when volt_name='交流35kV' and ifnull(l_ppq,0)>0 and tp_llr >= 0 and tp_llr<=5 then t1.volt_code

           when volt_name='交流110kV' and ifnull(l_ppq,0)>0 and tp_llr >= 0 and tp_llr<=3 then t1.volt_code

           when volt_name='交流220kV' and ifnull(l_ppq,0)>0 and tp_llr >= 0 and tp_llr<=1 then t1.volt_code

        end)) 分压正常数量

      ,count((case when volt_name='交流10kV' and (ifnull(l_ppq,0)=0 or tp_llr<0 or tp_llr>8) then t1.volt_code

           when volt_name='交流35kV' and (ifnull(l_ppq,0)=0 or tp_llr<0 or tp_llr>5) then t1.volt_code

           when volt_name='交流110kV' and (ifnull(l_ppq,0)=0 or tp_llr<0 or tp_llr>3) then t1.volt_code

           when volt_name='交流220kV' and (ifnull(l_ppq,0)=0 or tp_llr<0 or tp_llr>1) then t1.volt_code

        end)) 分压异常数量

      ,count((case when tp_llr<=-30 or tp_llr>=30 then t1.volt_code end)) `分压异常其中：正负30%以上`

      from (

          select distinct po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id,p.value volt_code,p.name volt_name

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

        ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

          from m_g_chkunit a

          join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

          join ac_org o on a.org_no=o.id

          join ac_org po on left(o.id,7)=po.id and length(po.id)=7 #and po.id like concat({组织},'%')

          join m_p_code p on b.obj_id=p.id

          where a.chkunit_type_code='03'

      ) t1

      left join (

          select a.org_no,b.volt_code,l_ppq ,l_spq ,l_ll_pq ,tp_llr

          from m_g_ll_stat a

          join m_g_ll_stat_byvolt b on a.id=b.stat_id

          where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

      ) xs on t1.gs_id=left(xs.org_no,7) and t1.volt_code=xs.volt_code

      group by gs_id

   ) x

) dydj_xs on xo.id=dydj_xs.gs_id

left join (

    select po.id gs_id,ifnull(count(distinct volt_id),0) 分压未配置考核单元数量

		from ac_org po

    ,(select 'AC00101' volt_code,'交流10kV' volt_name,96964149010435 volt_id union all

    select 'AC00351' volt_code,'交流35kV' volt_name,96964149010439 volt_id union all

    select 'AC01101' volt_code,'交流110kV' volt_name,96964149010442 volt_id

    ) dydj

		where length(po.id)=7  and not exists (select 1 from m_g_chkunit a1 , m_g_chkunit_comp b1 where a1.id=b1.chkunit_id and a1.chkunit_type_code=b1.obj_type_code and a1.chkunit_type_code='03' and b1.obj_id=dydj.volt_id)

    group by po.id

) dydj_kh on xo.id=dydj_kh.gs_id

where xo.type='0' and if(length({组织})<7,xo.id in ('5100121','5100116','5100125','5100123','5100434','5100105','5100109','5100122','5100423','5100118','5100108','5100113','5100120','5100112','5100110'),xo.id like concat({组织},'%'))

-- 文件名：线损情况统计_四分异常(分区域_未配置考核单元)
select po.name 县公司,o.name 供电单位

		from ac_org o

    join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id like concat({组织},'%')

		where o.type='0' and not exists (select 1 from m_g_chkunit a1 , m_g_chkunit_comp b1 where a1.id=b1.chkunit_id and a1.chkunit_type_code=b1.obj_type_code and a1.chkunit_type_code='04' and b1.obj_id=o.id)

-- 文件名：线损情况统计_四分异常(分压_异常正负30%以上)
select gs_name 县公司,volt_name 电压等级,l_ppq 合计供电量,l_spq 合计售电量,l_ll_pq 损失电量

,(case volt_code when 'AC00101' then '8%' when 'AC00351' then '5%' when 'AC01101' then '3%' when 'AC02201' then '1%' end) 考核值

,concat(round(tp_llr,2),'%') 线损率

from (

      select gs_id,gs_name,t1.volt_code,volt_name,l_ppq ,l_spq ,l_ll_pq ,tp_llr

      from (

          select distinct po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id,p.value volt_code,p.name volt_name

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

          from m_g_chkunit a

          join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

          join ac_org o on a.org_no=o.id

          join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id like concat({组织},'%')

          join m_p_code p on b.obj_id=p.id

          where a.chkunit_type_code='03'

      ) t1

      left join (

          select a.org_no,b.volt_code,l_ppq ,l_spq ,l_ll_pq ,tp_llr

          from m_g_ll_stat a

          join m_g_ll_stat_byvolt b on a.id=b.stat_id

          where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

      ) xs on t1.gs_id=left(xs.org_no,7) and t1.volt_code=xs.volt_code

) x where (tp_llr<=-30 or tp_llr>=30)

order by 1,2,3

-- 文件名：线损情况统计_四分异常(分压_异常其他)
select gs_name 县公司,volt_name 电压等级,l_ppq 合计供电量,l_spq 合计售电量,l_ll_pq 损失电量

,(case volt_code when 'AC00101' then '8%' when 'AC00351' then '5%' when 'AC01101' then '3%' when 'AC02201' then '1%' end) 考核值

,concat(round(tp_llr,2),'%') 线损率

from (

      select gs_id,gs_name,t1.volt_code,volt_name,l_ppq ,l_spq ,l_ll_pq ,tp_llr

      from (

          select distinct po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id,p.value volt_code,p.name volt_name

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

          from m_g_chkunit a

          join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

          join ac_org o on a.org_no=o.id

          join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id like concat({组织},'%')

          join m_p_code p on b.obj_id=p.id

          where a.chkunit_type_code='03'

      ) t1

      left join (

          select a.org_no,b.volt_code,l_ppq ,l_spq ,l_ll_pq ,tp_llr

          from m_g_ll_stat a

          join m_g_ll_stat_byvolt b on a.id=b.stat_id

          where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

      ) xs on t1.gs_id=left(xs.org_no,7) and t1.volt_code=xs.volt_code

) x

where (volt_name='交流10kV' and (ifnull(l_ppq,0)=0 or (tp_llr>-30 and tp_llr<0) or (tp_llr>8 and tp_llr<30)))

      or (volt_name='交流35kV' and (ifnull(l_ppq,0)=0 or (tp_llr>-30 and tp_llr<0) or (tp_llr>5 and tp_llr<30)))

      or (volt_name='交流110kV' and (ifnull(l_ppq,0)=0 or (tp_llr>-30 and tp_llr<0) or (tp_llr>3 and tp_llr<30)))

      or (volt_name='交流220kV' and (ifnull(l_ppq,0)=0 or (tp_llr>-30 and tp_llr<0) or (tp_llr>1 and tp_llr<30)))

order by 1,2,3

-- 文件名：线损情况统计_四分异常(分压_未配置考核单元)
select po.name 县公司,dydj.volt_name 电压等级

		from ac_org po

    ,(select 'AC00101' volt_code,'交流10kV' volt_name,96964149010435 volt_id union all

    select 'AC00351' volt_code,'交流35kV' volt_name,96964149010439 volt_id union all

    select 'AC01101' volt_code,'交流110kV' volt_name,96964149010442 volt_id -- union all

    -- select 'AC02201' volt_code,'交流220kV' volt_name,96964149010444 volt_id

    ) dydj

		where length(po.id)=7 and po.id like concat({组织},'%') and not exists (select 1 from m_g_chkunit a1 , m_g_chkunit_comp b1 where a1.id=b1.chkunit_id and a1.chkunit_type_code=b1.obj_type_code and a1.chkunit_type_code='03' and b1.obj_id=dydj.volt_id)

order by 1,2

-- 文件名：线损情况统计_四分异常(分台区_异常正负30%以上)
select gs_name 县公司,org_name 供电单位,tg_no 台区编码,tg_name 台区名称,t_ppq 合计供电量,t_spq 合计售电量,lpq 损失电量, concat(round(l_llr,2),'%') 线损率

from (

    select gs_name ,org_name,t1.tg_no,t1.tg_name ,t_ppq ,t_spq ,lpq ,l_llr

    from (

        select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id tg_id,tg_no,replace(replace(replace(replace(tg.tg_name,char(13),''),char(10),''),char(9),''),char(32),'') tg_name,p1.name pub_priv_flag

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

        from m_g_chkunit a

        join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

        join m_g_tg tg on b.obj_id=tg.id and tg.run_status_code='01'

        join ac_org o on a.org_no=o.id

        join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id like concat({组织},'%')

        left join m_p_code p1 on p1.code_type='pubPrivFlag' and p1.`value`=tg.pub_priv_flag

        where a.chkunit_type_code='02'

    ) t1

    left join (

        select a.org_no,tg.id tg_id,t_ppq ,t_spq ,lpq ,l_llr

        from m_g_ll_stat a

        join m_g_tg_ll_det b on a.id=b.stat_id

        join m_g_chkunit_comp c on b.tg_id=c.chkunit_id and c.obj_type_code='02'

        join m_g_tg tg on c.obj_id=tg.id and b.tg_no=tg.tg_no

        where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

    ) xs on t1.org_no=xs.org_no and t1.tg_id=xs.tg_id

) x where ( l_llr<=-30 or l_llr>=30)

order by 1,2

-- 文件名：线损情况统计_四分异常(分台区_异常其他)
select gs_name 县公司,org_name 供电单位,tg_no 台区编码,tg_name 台区名称,t_ppq 合计供电量,t_spq 合计售电量,lpq 损失电量, concat(round(l_llr,2),'%') 线损率

from (

    select gs_name ,org_name,t1.tg_no,t1.tg_name ,t_ppq ,t_spq ,lpq ,l_llr

    from (

        select po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id tg_id,tg_no,replace(replace(replace(replace(tg.tg_name,char(13),''),char(10),''),char(9),''),char(32),'') tg_name,p1.name pub_priv_flag

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

        from m_g_chkunit a

        join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

        join m_g_tg tg on b.obj_id=tg.id and tg.run_status_code='01'

        join ac_org o on a.org_no=o.id

        join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id like concat({组织},'%')

        left join m_p_code p1 on p1.code_type='pubPrivFlag' and p1.`value`=tg.pub_priv_flag

        where a.chkunit_type_code='02'

    ) t1

    left join (

        select a.org_no,tg.id tg_id,t_ppq ,t_spq ,lpq ,l_llr

        from m_g_ll_stat a

        join m_g_tg_ll_det b on a.id=b.stat_id

        join m_g_chkunit_comp c on b.tg_id=c.chkunit_id and c.obj_type_code='02'

        join m_g_tg tg on c.obj_id=tg.id and b.tg_no=tg.tg_no

        where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

    ) xs on t1.org_no=xs.org_no and t1.tg_id=xs.tg_id

) x where (ifnull(t_ppq,0)=0 or (l_llr>-30 and l_llr<0) or (l_llr>12 and l_llr<30))

order by 1,2

-- 文件名：线损情况统计_四分异常(分台区_未配置考核单元)
select po.name 县公司,o.name 供电单位,a.id 台区标识,a.tg_no 台区编码,replace(replace(replace(replace(a.tg_name,char(13),''),char(10),''),char(9),''),char(32),'') 台区名称,p1.name 公专变标识

		from m_g_tg a

    join ac_org o on a.org_no=o.id

    join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id like concat({组织},'%')

		left join m_p_code p1 on p1.code_type='pubPrivFlag' and p1.`value`=a.pub_priv_flag

		where a.run_status_code='01' and a.pub_priv_flag='01' and not exists (select 1 from m_g_chkunit a1 , m_g_chkunit_comp b1 where a1.id=b1.chkunit_id and a1.chkunit_type_code=b1.obj_type_code and a1.chkunit_type_code='02' and b1.obj_id=a.id)

-- 文件名：线损情况统计_四分异常(分线路_异常正负30%以上)
select gs_name 县公司,org_name 供电单位,volt_name 电压等级,line_no 线路编码,line_name 线路名称,t_ppq 合计供电量,t_spq 合计售电量,lpq 损失电量,考核值,concat(round(l_llr,2),'%') 线损率

 from (

    select gs_name ,org_name ,volt_name ,t1.line_no ,t1.line_name ,t_ppq ,t_spq ,lpq ,(case volt_code when 'AC00101' then '8%' when 'AC00351' then '5%' when 'AC01101' then '3%' when 'AC02201' then '1%' end) 考核值,l_llr

    from (

        select distinct po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id line_id,l.line_no,replace(replace(replace(replace(l.line_name,char(13),''),char(10),''),char(9),''),char(32),'') line_name,p.value volt_code,p.name volt_name

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

        from m_g_chkunit a

        join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

        join m_g_line l on b.obj_id=l.id and l.run_status_code='01'

        join ac_org o on a.org_no=o.id

        join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id like concat({组织},'%')

        left join m_p_code p on p.code_type='psVoltCode' and p.value=l.volt_code

        where a.chkunit_type_code='01'

    ) t1

    left join (

        select a.org_no,l.id line_id,t_ppq ,t_spq ,lpq ,l_llr

        from m_g_ll_stat a

        join (

          select stat_id,chkunit_org_no,line_id,line_no,line_name,t_ppq,t_spq,lpq,l_llr from m_g_llr_cmpl

          union all

          select stat_id,chkunit_org_no,line_id,line_no,line_name,t_ppq,t_spq,lpq,l_llr from m_g_llr_cmpl_highvolt

        ) b on a.id=b.stat_id

        join m_g_chkunit_comp c on b.line_id=c.chkunit_id and c.obj_type_code='01'

        join m_g_line l on c.obj_id=l.id and b.line_no=l.line_no

        left join m_p_code p on p.code_type='psVoltCode' and p.value=l.volt_code

        where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

    ) xs on t1.org_no=xs.org_no and t1.line_id=xs.line_id

) x where (l_llr<=-30 or l_llr>=30)

  order by 1,2,3

-- 文件名：线损情况统计_四分异常(分线路_异常其他)
select gs_name 县公司,org_name 供电单位,volt_name 电压等级,line_no 线路编码,line_name 线路名称,t_ppq 合计供电量,t_spq 合计售电量,lpq 损失电量,考核值,concat(round(l_llr,2),'%') 线损率

 from (

    select gs_name ,org_name ,volt_name ,t1.line_no ,t1.line_name ,t_ppq ,t_spq ,lpq ,(case volt_code when 'AC00101' then '8%' when 'AC00351' then '5%' when 'AC01101' then '3%' when 'AC02201' then '1%' end) 考核值,l_llr

    from (

        select distinct po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id line_id,l.line_no,replace(replace(replace(replace(l.line_name,char(13),''),char(10),''),char(9),''),char(32),'') line_name,p.value volt_code,p.name volt_name

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

          ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

        from m_g_chkunit a

        join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

        join m_g_line l on b.obj_id=l.id and l.run_status_code='01'

        join ac_org o on a.org_no=o.id

        join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id like concat({组织},'%')

        left join m_p_code p on p.code_type='psVoltCode' and p.value=l.volt_code

        where a.chkunit_type_code='01'

    ) t1

    left join (

        select a.org_no,l.id line_id,t_ppq ,t_spq ,lpq ,l_llr

        from m_g_ll_stat a

        join (

          select stat_id,chkunit_org_no,line_id,line_no,line_name,t_ppq,t_spq,lpq,l_llr from m_g_llr_cmpl

          union all

          select stat_id,chkunit_org_no,line_id,line_no,line_name,t_ppq,t_spq,lpq,l_llr from m_g_llr_cmpl_highvolt

        ) b on a.id=b.stat_id

        join m_g_chkunit_comp c on b.line_id=c.chkunit_id and c.obj_type_code='01'

        join m_g_line l on c.obj_id=l.id and b.line_no=l.line_no

        left join m_p_code p on p.code_type='psVoltCode' and p.value=l.volt_code

        where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

    ) xs on t1.org_no=xs.org_no and t1.line_id=xs.line_id

) x

where (volt_name='交流10kV' and (ifnull(t_ppq,0)=0 or (l_llr>-30 and l_llr<0) or (l_llr>8 and l_llr<30)))

      or (volt_name='交流35kV' and (ifnull(t_ppq,0)=0 or (l_llr>-30 and l_llr<0) or (l_llr>5 and l_llr<30)))

      or (volt_name='交流110kV' and (ifnull(t_ppq,0)=0 or (l_llr>-30 and l_llr<0) or (l_llr>3 and l_llr<30)))

      or (volt_name='交流220kV' and (ifnull(t_ppq,0)=0 or (l_llr>-30 and l_llr<0) or (l_llr>1 and l_llr<30)))

order by 1,2,3

-- 文件名：线损情况统计_四分异常(分线路_未配置考核单元)
select po.name 县公司,o.name 供电单位,p.name 电压等级

      ,a.id 线路标识,a.line_no 线路编码,replace(replace(replace(replace(a.line_name,char(13),''),char(10),''),char(9),''),char(32),'') 线路名称

		from m_g_line a

    join ac_org o on a.org_no=o.id

    join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id like concat({组织},'%')

    left join m_p_code p on p.code_type='psVoltCode' and p.value=a.volt_code

		where a.run_status_code='01' and not exists (select 1 from m_g_chkunit a1 , m_g_chkunit_comp b1 where a1.id=b1.chkunit_id and a1.chkunit_type_code=b1.obj_type_code and a1.chkunit_type_code='01' and b1.obj_id=a.id)

order by 1,2,3

-- 文件名：线损情况统计_四分异常(分区域_异常正负30%以上)
select gs_name 县公司,org_name 供电单位,g_ppq 供电量,g_spq 售电量,g_ll_pq 线损电量,'12%' 考核值,concat(round(g_llr,2),'%') 线损率

from (select gs_name,org_name,g_ppq ,g_spq ,g_ll_pq ,g_llr

    from (

           select distinct po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id

            ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

            ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

          from m_g_chkunit a

          join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

          join ac_org o on a.org_no=o.id

          join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id like concat({组织},'%')

          where a.chkunit_type_code='04'

        ) t1

        left join (

            select a.org_no,g_ppq ,g_spq ,g_ll_pq ,g_llr

            from m_g_ll_stat a

            join m_g_g_ll_stat b on a.id=b.stat_id

            where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

    ) xs on t1.org_no=xs.org_no

) x where (g_llr<=-30 or g_llr>=30)

order by 1,2

-- 文件名：线损情况统计_四分异常(分区域_异常其他)
select gs_name 县公司,org_name 供电单位,g_ppq 供电量,g_spq 售电量,g_ll_pq 线损电量,'12%' 考核值,concat(round(g_llr,2),'%') 线损率

from (select gs_name,org_name,g_ppq ,g_spq ,g_ll_pq ,g_llr

    from (

            select distinct po.id gs_id,po.`name` gs_name,o.id org_no,o.`name` org_name,a.id chkunit_id,a.chkunit_name,b.obj_id

            ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='01') gdl_comp

            ,(select count(id) from m_g_io_mp where chkunit_id=a.id and gspq_comp_type='02') sdl_comp

            from m_g_chkunit a

            join m_g_chkunit_comp b on a.id=b.chkunit_id and a.chkunit_type_code=b.obj_type_code

            join ac_org o on a.org_no=o.id

            join ac_org po on left(o.id,7)=po.id and length(po.id)=7 and po.id like concat({组织},'%')

            where a.chkunit_type_code='04'

        ) t1

        left join (

            select a.org_no,g_ppq ,g_spq ,g_ll_pq ,g_llr

            from m_g_ll_stat a

            join m_g_g_ll_stat b on a.id=b.stat_id

            where a.bgn_date>=DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d') and a.end_date<date_add(DATE_FORMAT(concat({年月} ,'01'),'%Y-%m-%d'), interval 1 month) and a.data_status='01'

    ) xs on t1.org_no=xs.org_no

) x where (ifnull(g_ppq,0)=0 or (g_llr>-30 and g_llr<0) or (g_llr>12 and g_llr<30))

order by 1,2

-- 文件名：线路台区电量-按供电所
SELECT

	o1.NAME AS 用户单位,

	( SELECT NAME FROM ac_org WHERE CODE = ( SELECT l.org_no FROM m_g_line l WHERE id = a.line_id ) ) 线路单位,

	gl2.line_no AS 线路编号,

	gl1.line_name AS 线路名称,

	gt2.tg_no AS 台区编号,

	gt1.tg_name AS 台区名称,

	(

	SELECT NAME

	FROM

		m_p_code


LEFT JOIN ac_org o1 ON CODE = a.org_no
LEFT JOIN m_g_line gl2 ON id = a.line_id
LEFT JOIN m_g_line gl1 ON id = a.line_id
LEFT JOIN m_g_tg gt2 ON id = a.tg_id
LEFT JOIN m_g_tg gt1 ON id = a.tg_id
	WHERE

		code_type = 'pubPrivFlag'

	AND

	VALUE

		= ( SELECT g.pub_priv_flag FROM m_g_tg g WHERE id = a.tg_id )

	) 专公变标识,

	ifnull(sum( d.settle_apq ) ,0) 售电量

FROM

	m_e_mp_para_snap_arc a

	LEFT JOIN m_e_mp_pq_arc d ON a.id = d.mp_para_snap_id

	AND a.ym = d.ym

	WHERE 1=1

  and a.org_No={用户供电单位}

  and a.ym={电费年月}

group by a.line_id,a.tg_id

-- 文件名：线路台区电量明细-供电所
SELECT

c.cons_no 户号,

c.cons_name 户名,

	o1.NAME AS 用户单位,

	( SELECT NAME FROM ac_org WHERE CODE = ( SELECT l.org_no FROM m_g_line l WHERE id = a.line_id ) ) 线路单位,

	gl2.line_no AS 线路编号,

	gl1.line_name AS 线路名称,

	gt2.tg_no AS 台区编号,

	gt1.tg_name AS 台区名称,

	(

	SELECT NAME

	FROM

		m_p_code

	WHERE

		code_type = 'pubPrivFlag'

	AND

	VALUE

		= ( SELECT g.pub_priv_flag FROM m_g_tg g WHERE id = a.tg_id )

	) 专公变标识,

	  ifnull(d.settle_apq ,0)  售电量

FROM

	m_e_mp_para_snap_arc a

	LEFT JOIN m_e_mp_pq_arc d ON a.id = d.mp_para_snap_id

	AND a.ym = d.ym

	LEFT JOIN m_e_cons_snap_arc c ON c.ym = a.ym

	AND c.id = a.calc_id


LEFT JOIN ac_org o1 ON CODE = c.org_no
LEFT JOIN m_g_line gl2 ON id = a.line_id
LEFT JOIN m_g_line gl1 ON id = a.line_id
LEFT JOIN m_g_tg gt2 ON id = a.tg_id
LEFT JOIN m_g_tg gt1 ON id = a.tg_id
WHERE 1=1

  and c.org_No={用户供电单位}

  and a.ym={电费年月}

  and a.tg_id in(ifnull((select id from m_g_tg where tg_no={台区编码--可不写}),a.tg_id ))

	and a.line_id in(ifnull((select id from m_g_line where line_no={线路编码}),a.line_id))

-- 文件名：合江大工业执行工商业两部制1-10千伏电价用户
select o.`name` 供电单位,a.cons_no 用户编号,a.cons_name 用户名称,a.elec_addr 用电地址,zdl.elec_type 电价用电类别

  ,zdl.prc_code 电价码,zdl.cat_prc_name 电价名称,zdl.ym 电费年月

  ,zdl.pq 总电量,zdl.amt 总电费

  ,sd.pq_j 尖电量,sd.cat_amt_j 尖目录电费

  ,sd.pq_f 峰电量,sd.cat_amt_f 峰目录电费

  ,sd.pq_p 平电量,sd.cat_amt_p 平目录电费

  ,sd.pq_g 谷电量,sd.cat_amt_g 谷目录电费

  ,ba.ba 基本电费,gl.pf_adj_amt 力调电费,zdl.pl_amt 代征基金

from m_c_cons a

join ac_org o on a.org_no=o.id

join (

  select a.cons_no,a.ym,b.prc_code,c.cat_prc_name,p1.`name` elec_type

    ,sum(b.t_settle_pq) pq

    ,sum(b.t_amt) amt

    ,sum(b.t_pl_amt) pl_amt

    ,count(distinct a.id) calc_nums,max(a.send_date) send_date

  from m_e_cons_snap_arc a

  join m_e_cons_prc_amt_arc b on a.id=b.calc_id

  left join m_e_cat_prc c on b.para_vn=c.para_vn and b.prc_code=c.prc_code

  left join m_p_code p1 on p1.code_type='elecTypeCode' and p1.`value`=b.elec_type_code

  where a.org_no like concat({管理单位}, '%')

    and a.ym={年月}

    and left(b.elec_type_code,1)='1'

    and b.prc_code={电价码}

  group by a.cons_no,a.ym,b.prc_code,c.cat_prc_name

) zdl on a.cons_no=zdl.cons_no

left join (

  select a.cons_no,a.ym,b.prc_code

    ,sum(case when c.prc_ts_code='01' then c.settle_apq end) pq_j

    ,sum(case when c.prc_ts_code='02' then c.settle_apq end) pq_f

    ,sum(case when c.prc_ts_code='03' then c.settle_apq end) pq_p

    ,sum(case when c.prc_ts_code='04' then c.settle_apq end) pq_g

    ,sum(case when c.prc_ts_code='01' then c.cat_kwh_amt+c.flat_bal end) cat_amt_j

    ,sum(case when c.prc_ts_code='02' then c.cat_kwh_amt+c.flat_bal end) cat_amt_f

    ,sum(case when c.prc_ts_code='03' then c.cat_kwh_amt+c.flat_bal end) cat_amt_p

    ,sum(case when c.prc_ts_code='04' then c.cat_kwh_amt+c.flat_bal end) cat_amt_g

    ,sum(case when c.prc_ts_code='01' then c.kwh_amt end) amt_j

    ,sum(case when c.prc_ts_code='02' then c.kwh_amt end) amt_f

    ,sum(case when c.prc_ts_code='03' then c.kwh_amt end) amt_p

    ,sum(case when c.prc_ts_code='04' then c.kwh_amt end) amt_g

    ,sum(case when ifnull(c.prc_ts_code,'') not in('01','02','03','04') then c.cat_kwh_amt end) amt_o

  from m_e_cons_snap_arc a

  join m_e_cons_prc_amt_arc b on a.id=b.calc_id

  join m_e_kwh_amt_arc c on b.id=c.prc_amt_id

  where a.org_no like concat({管理单位}, '%')

    and a.ym={年月}

    and left(b.elec_type_code,1)='1'

    and b.prc_code={电价码}

  group by a.cons_no,a.ym,b.prc_code

) sd on zdl.cons_no=sd.cons_no and zdl.ym=sd.ym and zdl.prc_code=sd.prc_code

left join (

  select a.cons_no,a.ym,b.prc_code

    ,round(sum(c.ba),2) ba

  from m_e_cons_snap_arc a

  join m_e_cons_prc_amt_arc b on a.id=b.calc_id

  join m_e_base_amt_arc c on b.id=c.prc_amt_id

  where a.org_no like concat({管理单位}, '%')

    and a.ym={年月}

    and left(b.elec_type_code,1)='1'

    and b.prc_code={电价码}

  group by a.cons_no,a.ym,b.prc_code

) ba on zdl.cons_no=ba.cons_no and zdl.ym=ba.ym and zdl.prc_code=ba.prc_code

left join (

  select a.cons_no,a.ym,b.prc_code

    ,group_concat(distinct concat(0+convert(c.adj_factor,char))) adj_factor

    ,round(sum(c.pf_adj_amt),2) pf_adj_amt

  from m_e_cons_snap_arc a

  join m_e_cons_prc_amt_arc b on a.id=b.calc_id

  join m_e_pf_amt_arc c on b.id=c.prc_amt_id and c.pf_adj_amt<>0

  where a.org_no like concat({管理单位}, '%')

    and a.ym={年月}

    and left(b.elec_type_code,1)='1'

    and b.prc_code={电价码}

  group by a.cons_no,a.ym,b.prc_code

) gl on zdl.cons_no=gl.cons_no and zdl.ym=gl.ym and zdl.prc_code=gl.prc_code

where a.org_no like concat({管理单位}, '%')

order by zdl.ym,a.cons_no,a.cons_name

-- 文件名：账期起始时间查询
select  DATE_FORMAT(effect_time, '%Y-%m-%d %H:%i:%s') 生效时间,

DATE_FORMAT(ifnull(expire_time,now()), '%Y-%m-%d %H:%i:%s') 失效时间

from m_p_syspara_value

        where para_id in (select id from m_p_syspara  where para_code = 'AMTYM')

        and org_no = {供电单位}

        and value={电费年月}

-- 文件名：未开具电子发票用户信息查询
SELECT DISTINCT

			o1.name AS 单位,

    	rs1.`name` AS 抄表段,

			cons.cons_no 用户编号,

			cons.cons_name  用户名称,

			cons.elec_addr 用电地址,

			p3.`name` AS 用电类别,

			(select  line.line_name from m_c_mp mp,m_g_line line where mp.cons_id=cons.id and mp.line_id = line.id  order by mp.run_date desc	limit 1) 线路,

			(select  tg.tg_name from m_c_mp mp,m_g_tg tg where mp.cons_id=cons.id and mp.tg_id = tg.id  order by mp.run_date desc	limit 1) 台区,

			p2.`name` AS 用户分类,

			p1.`name` AS 用户状态

			from   m_c_cons cons

			INNER JOIN m_c_vat  vat on cons.vat_id=vat.id and vat.note_type_code in ('02','06')

			left join m_a_rcvbl_flow flow on flow.cons_no=cons.cons_no and flow.rcvbl_ym={电费年月}

			left join m_a_rcvbl_flow_arc flow_arc on flow_arc.cons_no=cons.cons_no and flow_arc.rcvbl_ym={电费年月}

			left join m_a_note_info note  on cons.cons_no=note.cons_no and note.amt_ym = {电费年月}


LEFT JOIN ac_org o1 ON id = cons.org_no
LEFT JOIN m_r_sect rs1 ON id = cons.mr_sect_no
LEFT JOIN m_p_code p3 ON code_type='elecTypeCode' and `value`= cons.elec_type_code AND take_effect_flag = 1
LEFT JOIN m_p_code p2 ON code_type='custSortCode' and `value`= cons.cons_sort_code AND take_effect_flag = 1
LEFT JOIN m_p_code p1 ON code_type='statusCode' and `value`= cons.status_code AND take_effect_flag = 1
		WHERE

    	cons.status_code<>'9' and cons.org_no like concat({单位},'%') and (note.id is null or note.`status`<>'01')

			and (flow.id is not null or flow_arc.id is not null)

-- 文件名：上网电量结算汇总
SELECT o1.name AS 管理单位,

amt.年月,

amt.发电厂编号,

amt.发电厂名称,

amt.企业编号,

amt.企业名称,

amt.管理机构,

amt.抄见有功电量,

amt.线损电量,

amt.拒购电量,

amt.过网电量,

amt.结算有效电量,

amt.网内收购电量,

amt.网内收购电费,

amt.网外代销电量,

amt.网外代销电费,

amt.无功考核电量,

amt.超欠发无功电费,

amt.税率,

amt.税费,

amt.税后电费,

amt.应付电费,

amt.应收过网费,

amt.发电电量,

amt.上网电量,

if(amt.发电电量=0,0,round((amt.发电电量-amt.上网电量)/amt.发电电量,2)) 厂用率 FROM (SELECT amt.*,

            IFNULL((SELECT

                    sum(q.settle_apq)

                FROM

                    m_e_mp_pq_arc q

                LEFT JOIN m_e_mp_para_snap_arc p ON p.id = q.mp_para_snap_id

                AND p.usage_type_code = '1101'

                WHERE

                    p.calc_id = amt.id),0) 发电电量,

IFNULL((SELECT

                    sum(q.settle_apq)

                FROM

                    m_e_mp_pq_arc q

                LEFT JOIN m_e_mp_para_snap_arc p ON p.id = q.mp_para_snap_id

                AND p.usage_type_code = '1102'

                WHERE

                    p.calc_id = amt.id),0) 上网电量 FROM (SELECT

                    t.id,t.org_no,

t.年月,

t.发电厂编号,

t.发电厂名称,

t.企业编号,

t.企业名称,

t.抄见有功电量,

t.线损电量,

t.拒购电量,

t.过网电量,

SUM(if(b.amt_type='200' or b.amt_type='201',IFNULL(b.T_SETTLE_PQ, 0),0)) 结算有效电量,

SUM(if(b.amt_type='201',IFNULL(b.T_SETTLE_PQ, 0),0)) 网内收购电量,

SUM(if(b.amt_type='201',IFNULL(b.T_AMT, 0),0)) 网内收购电费,

SUM(if(b.amt_type='200',IFNULL(b.T_SETTLE_PQ, 0),0)) 网外代销电量,

SUM(if(b.amt_type='200',IFNULL(b.T_AMT, 0),0)) 网外代销电费,

t.无功考核电量,

SUM(if(b.amt_type='204',IFNULL(b.T_AMT, 0),0)) 超欠发无功电费,

round(SUM(if(b.amt_type='200' or b.amt_type='201' or b.amt_type='204',IFNULL(b.T_AMT, 0),0))

-round(SUM(if(b.amt_type='200' or b.amt_type='201' or b.amt_type='204',

IFNULL(b.T_AMT, 0),0)) / (1+ifnull(c.value_added_tax,0)),2),2) 税费,

round(SUM(if(b.amt_type='200' or b.amt_type='201' or b.amt_type='204',

	IFNULL(b.T_AMT, 0),0)) / (1+ifnull(c.value_added_tax,0)),2) 税后电费,

SUM(if(b.amt_type='200' or b.amt_type='201' or b.amt_type='204',IFNULL(b.T_AMT, 0),0)) 应付电费,

SUM(if(b.amt_type='202',IFNULL(b.T_AMT, 0),0)) 应收过网费,

(select name from m_p_code where code_type = 'manageAgencyTypeCode' and `value` = c.manage_agency limit 1) 管理机构,

CONCAT(ROUND(c.value_added_tax * 100, 0), '%') 税率

FROM (

SELECT

c.id,

c.gc_id,

c.org_no,

a.amt_ym 年月,

c.gc_no 发电厂编号,

c.gc_name 发电厂名称,

d.geg_no 企业编号,

d.geg_name 企业名称,

sum(ifnull(mp.flaten_apq,0)) 抄见有功电量,

sum(ifnull(mp.ap_ll,0)) 线损电量,

sum(ifnull(mp.rfspuh_share_pq,0)) 拒购电量,

sum(ifnull(mp.ssu_pq,0)) 过网电量,

sum(ifnull(mp.check_rp,0)) 无功考核电量

FROM m_r_plan_arc a

INNER JOIN m_r_sect b ON a.mr_sect_no = b.id AND b.attr='23'

INNER JOIN m_e_gc_snap_arc c ON a.app_no = c.app_code

INNER JOIN m_c_fc_geg_gc_rela rela ON rela.gc_id = c.gc_id

inner join m_c_fc_geg d on d.id = rela.geg_id

INNER JOIN m_e_mp_para_snap_arc e ON c.id = e.calc_id  AND e.data_src not in ('99','98')

left JOIN m_e_fc_mp_pq_det_arc mp ON mp.mp_para_snap_id = e.id


LEFT JOIN ac_org o1 ON id = amt.org_no
where c.ym={电费年月} AND IF({管理单位}='',1=1,c.org_no  like concat({管理单位}, '%'))

GROUP BY c.id) t

INNER JOIN  m_e_cons_prc_amt_arc b	ON t.ID = b.CALC_ID

inner JOIN  m_c_fc_gc c	ON t.gc_id = c.id

GROUP BY t.id) amt) amt

-- 文件名：合江走收抄表段打印状态信息
SELECT

	o1.NAME AS 供电单位,

	rbl.mr_sect_no 抄表段编号,

(select CONCAT_WS( '-', login_name, user_name ) from ac_user where login_name= (select c.operator_no from m_r_oper_activity c

				WHERE

					c.mr_sect_no = rbl.mr_sect_no

					AND c.effect_flag = '1'

					AND c.act_code = '03' limit 1)) 抄表员,

	 bln 在途户数,

	edn 销账户数,

	( bln - edn ) 未销账户数,

if(bln is null or bln='','未打印','打印完毕') 打印状态

FROM

	(

	SELECT

		org_no,

		mr_sect_no

	FROM

		(

			(

			SELECT

				a.org_no,

				mr_sect_no

			FROM

				m_a_rcvbl_flow a

			WHERE

				a.org_no = {供电单位}

				AND rcvbl_ym = {电费年月}

				AND pay_mode = '010201'

				AND EXISTS (

				SELECT

					1

				FROM

					m_r_oper_activity c

				WHERE

					c.mr_sect_no = a.mr_sect_no

					AND c.effect_flag = '1'

					AND c.act_code = '03'

					AND c.operator_no = IF

	( {抄表员工号} IS NULL OR {抄表员工号} = '', c.operator_no,{抄表员工号} )

				)

			) UNION ALL

			(

			SELECT

				a.org_no,

				mr_sect_no

			FROM

				m_a_rcvbl_flow_arc a

			WHERE

				a.org_no =  {供电单位}

				AND rcvbl_ym = {电费年月}

				AND pay_mode = '010201'

				AND EXISTS (

				SELECT

					1

				FROM

					m_r_oper_activity c

				WHERE

					c.mr_sect_no = a.mr_sect_no

					AND c.effect_flag = '1'

					AND c.act_code = '03'

					AND c.operator_no = IF

	( {抄表员工号} IS NULL OR {抄表员工号} = '', c.operator_no,{抄表员工号} )

				)

			)

		) aa

	GROUP BY

		mr_sect_no

	) rbl

	LEFT JOIN (

	SELECT

		org_no,

		sit.mr_sect_no,

		sum( sit.transit_num ) bln,

		sum( sit.t_rcved_num ) edn

	FROM

		m_a_transit sit


LEFT JOIN ac_org o1 ON o1.id = rbl.org_no
	WHERE

		org_no =  {供电单位}

and exists(select 1 from m_a_transit_det ff where ff.transit_id=sit.id and ff.rcvbl_ym={电费年月} )

	GROUP BY

		org_no,

		sit.mr_sect_no

	) blsit ON blsit.org_no = rbl.org_no

	AND blsit.mr_sect_no = rbl.mr_sect_no

-- 文件名：走收在途欠费结清
SELECT

  o1.name AS 用户单位,

	fox.sitid 走收在途编号,

fox.mr_sect_no 抄表段,

	fox.cons_no 户号,

	fox.t_transit_amt 在途电费,

	fox.RCVED_AMT 实收电费,

	p3.name AS 发行结清标识,

	sf.CHARGE_EMP_NO 收费人员,

	p2.name AS 缴费方式,

	p1.name AS 结算方式

FROM

	(

	SELECT

	 det.org_no,

		sit.id sitid,

sit.mr_sect_no,

		det.rcvbl_amt_id,

		det.cons_no,

		det.t_transit_amt,

		det.RCVED_AMT,

		aa.settle_flag,

		aa.id

	FROM

		m_a_transit sit,

		m_a_transit_det det,

		(

			(

			SELECT

				a.id,

				a.rcvbl_amt,

				a.rcved_amt,

				( a.rcvbl_amt - a.rcved_amt ) qianfei,

				a.settle_flag

			FROM

				m_a_rcvbl_flow a

			WHERE

				a.org_no ={供电单位}

				AND rcvbl_ym = {电费年月}

				AND pay_mode = '010201'

				AND EXISTS (

				SELECT

					1

				FROM

					m_r_oper_activity c

				WHERE

					c.mr_sect_no = a.mr_sect_no

					AND c.effect_flag = '1'

					AND c.act_code = '03'

					AND c.operator_no =

				IF

					( {抄表员工号} IS NULL OR {抄表员工号} = '', c.operator_no,{抄表员工号} )

				)

				AND a.settle_flag <> '01'

			) UNION ALL

			(

			SELECT

				a.id,

				a.rcvbl_amt,

				a.rcved_amt,

				( a.rcvbl_amt - a.rcved_amt ) qianfei,

				a.settle_flag

			FROM

				m_a_rcvbl_flow_arc a

			WHERE

				a.org_no ={供电单位}

				AND rcvbl_ym = {电费年月}

				AND pay_mode = '010201'

				AND EXISTS (

				SELECT

					1

				FROM

					m_r_oper_activity c

				WHERE

					c.mr_sect_no = a.mr_sect_no

					AND c.effect_flag = '1'

					AND c.act_code = '03'

					AND c.operator_no =

				IF

					( {抄表员工号} IS NULL OR {抄表员工号} = '', c.operator_no,{抄表员工号} )

				)

				AND a.settle_flag <> '01'

			)

		) aa


LEFT JOIN ac_org o1 ON code =fox.org_no
LEFT JOIN m_p_code p3 ON code_type='settleFlag' and value=fox.settle_flag AND take_effect_flag = 1
LEFT JOIN m_p_code p2 ON code_type='payMode' and value=sf.pay_mode AND take_effect_flag = 1
LEFT JOIN m_p_code p1 ON code_type='settleMode' and value=sf.settle_mode AND take_effect_flag = 1
	WHERE 1=1

		-- and det.cons_no = '010820001551'

		AND det.rcvbl_ym = {电费年月}

		AND det.t_transit_amt <> IFNULL(det.rcved_amt,0)

		AND sit.id = det.transit_id

   	and aa.id=det.rcvbl_amt_id

		AND sit.pay_mode = '010201'

		AND det.org_no ={供电单位}

	) fox

	LEFT JOIN (

	SELECT

		flow.CHARGE_EMP_NO,

		flow.pay_mode,

		flow.settle_mode,

		ed.rcvbl_amt_id

	FROM

		m_a_pay_flow flow,

		m_a_rcved_flow ed

	WHERE

		flow.id = ed.charge_id

		AND ed.rcvbl_ym = {电费年月}

		AND flow.correct_id IS NULL

		AND flow.org_no ={供电单位}

	) sf ON fox.id = sf.rcvbl_amt_id

-- 文件名：远采集抄抄表止度与1号0点采集冻结示数不一致信息
select distinct

	o.name 单位,sect.id 抄表段编号,sect.name 抄表段名称,'用户' 分类,cons.cons_no 户号,cons.cons_name 户名,cons.elec_addr 用电地址,cm.made_no 表号,rd.t_factor 倍率,rd.last_mr_num 抄见起度,rd.this_read 抄见止度,this_read_pq 抄见电量,date_format(this_ymd,'%Y%m%d') 抄表日期,p1.name 抄表方式,col.createDate 采集日期,col.total 采集有功总,round(rd.this_read-col.total,2) 止度差额

	from m_c_cons cons

	join ac_org o on cons.org_no=o.id and o.id={组织}

	join m_r_data_arc rd on cons.cons_no=rd.cons_no and amt_ym={电费年月} and rd.read_type_code='11' and rd.actual_mode='301'

	join m_c_meter cm on rd.meter_id=cm.id and rd.mp_id=cm.mp_id

	join collect_data.col_d_active_energy_2024 col on col.consNo=rd.cons_no and	col.address=cm.made_no_int and col.createDate=LAST_DAY(DATE_SUB(this_ymd, INTERVAL 1 MONTH)) and col.total<>rd.this_read

	left join m_r_sect sect on cons.mr_sect_no=sect.id

	left join m_p_code p1 on p1.code_type='mrModeCode' and p1.value=rd.actual_mode

	where cons.status_code<>'9' and exists (select 1 from m_c_mp mp where mp.type_code='01' and mp.status_code in ('01','02') and mp.cons_id=cons.id)

	union all

	select distinct

	o.name 单位,sect.id 抄表段编号,sect.name 抄表段名称,p3.name 分类,mp.mp_no 户号,mp.mp_name 户名,mp.mp_addr 用电地址,cm.made_no 表号,rd.t_factor 倍率,rd.last_mr_num 起度,rd.this_read 止度,this_read_pq 抄见电量,date_format(this_ymd,'%Y%m%d') 抄表日期,p1.name 抄表方式,col.createDate 采集日期,col.total 采集有功总,round(rd.this_read-col.total,2) 止度差额

	from m_c_mp mp

	join ac_org o on mp.org_no=o.id and o.id={组织}

	join m_r_data_arc rd on mp.id=rd.mp_id and amt_ym={电费年月} and rd.read_type_code='11' and rd.actual_mode='301'

	join m_c_meter cm on rd.meter_id=cm.id and rd.mp_id=cm.mp_id

	join collect_data.col_d_active_energy_2024 col on col.consNo=rd.cons_no and	col.address=cm.made_no_int and col.createDate=LAST_DAY(DATE_SUB(this_ymd, INTERVAL 1 MONTH)) and col.total<>rd.this_read

	left join m_r_sect sect on mp.mr_sect_no=sect.id

	left join m_p_code p1 on p1.code_type='mrModeCode' and p1.value=rd.actual_mode

	left join m_p_code p3 on p3.code_type='mpSortCode' and p3.value=mp.type_code

	where mp.type_code<>'01' and mp.status_code in ('01','02')

	order by 1,2,4

-- 文件名：有采集点无采集对象
SELECT

 o1.name AS 供电单位,

 c.cons_no 户号,

 c.cons_name 户名,

 c.elec_addr 地址,

 p2.name AS 费控类型,

 p1.name AS 用户分类,

 cp.cp_no 采集点编号,

 cp.`name` 采集点名称

 FROM

  m_c_cons c

inner join m_r_cp_cons_rela rela on rela.cons_id = c.id

INNER JOIN m_r_cp cp on cp.cp_no = rela.cp_no

inner join m_c_meter cm on c.id = cm.cons_id

left join m_r_coll_obj obj on obj.meter_id = cm.id  and c.id = obj.cons_id


LEFT JOIN ac_org o1 ON code =c.org_no
LEFT JOIN m_p_code p2 ON code_type='ctlMode' and value=c.ctl_mode AND take_effect_flag = 1
LEFT JOIN m_p_code p1 ON code_type='custSortCode' and value=c.cons_sort_code AND take_effect_flag = 1
 WHERE

1 = 1

  and c.status_code <> '9' and obj.id is null

    AND c.org_no = {供电单位}

group by c.id

ORDER BY

 cp.cp_no,

 c.cons_no

-- 文件名：长宁关联户电量电费查询
select

       a.供电单位 供电所,a.用户户号 户号,a.用户户名 户名,{电费年月} 电费年月,

       dd.prc_start 起码, dd.prc_end 止码,dd.prc_bl 倍率,dd.sec_pq 抄见电量,a.总电量-dd.total_pq 加减电量,a.总电量 计费电量,aa.prc 电价,a.总电费 电费,round(a.总电费/a.总电量,3) 均价

from (

	select a.id,co.name 供电单位 ,a.cons_no 用户户号,a.cons_name 用户户名,a.mr_sect_no 抄表段, a.volt_code 供电电压,b.prc_code 电价码,

					sum(ifnull(c.t_settle_pq, 0)) 总电量,sum(ifnull(c.t_amt, 0)) 总电费

	FROM m_e_Cons_Snap_Arc a

	join m_c_cons acons on a.cons_id=acons.id

	join m_c_cons zh on acons.tmp_pay_rela_no=zh.cons_no

	left join ac_org co on a.org_no=co.code

	LEFT JOIN m_e_Consprc_Snap_Arc b on a.id=b.calc_id

	LEFT JOIN m_e_Cons_Prc_Amt_Arc c on a.id=c.calc_id

	where b.id=c.prc_snap_id

	and a.org_no like concat({组织},'%')

	and b.org_no like concat({组织},'%')

	and c.org_no like concat({组织},'%')

	and a.ym={电费年月}

	and b.ym={电费年月}

	and c.ym={电费年月}

        and zh.cons_no={主户号}

	group by a.cons_no) a

left join (select calc_id,group_concat(t_factor)  prc_bl,

                        group_concat(r.last_mr_num) prc_start,

                        group_concat(r.this_read) prc_end,

                        group_concat(r.this_read_pq) sec_pq,

                        sum(r.this_read_pq) total_pq,

                        r.org_no,r.cons_no

                        from m_r_data_arc r

                        join m_c_cons  acons on r.cons_no=acons.cons_no

												join m_c_cons zh on acons.tmp_pay_rela_no=zh.cons_no

                        where  r.org_no like concat({组织},'%')

                        and r.amt_ym={电费年月} and read_type_code='11' and zh.cons_no={主户号}

     group by calc_id) dd on a.id=dd.calc_id

 join (select p1.name useele,prc.cat_prc_abbr,prc.prc_code,max(det.kwh_prc) prc,p2.name voltname

                    from m_p_code p1,

                    m_p_code p2,

                    m_e_cat_prc prc,

                    m_e_cat_prc_det det

                    where p1.code_type='elecTypeCode'

                    and p2.code_type='prcVoltCode'

                    and p1.value=prc.elec_type_code

                    and p2.value=prc.prc_volt_code

                    and det.cat_prc_id=prc.id

                    -- and p1.p_code is null

                     group by prc.prc_code)aa on aa.prc_code=a.电价码

 order by a.用户户名

