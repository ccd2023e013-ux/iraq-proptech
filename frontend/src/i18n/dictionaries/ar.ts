// Arabic is the source-of-truth dictionary; English must provide the same keys.
const ar = {
  meta: {
    title: "عقار العراق — منصة العقارات الذكية",
    description: "منصة عراقية للبحث عن العقارات وبيعها وتأجيرها، مع خرائط وتحليلات ذكية.",
  },
  nav: {
    home: "الرئيسية",
    properties: "العقارات",
    map: "الخريطة",
    login: "تسجيل الدخول",
    switchLanguage: "English",
  },
  home: {
    badge: "قيد التطوير",
    title: "منصة العقارات العراقية",
    subtitle:
      "بيع وشراء وتأجير العقارات في البصرة وجميع المحافظات، مع بحث على الخريطة وتحليل ذكي لا يخترع المعلومات.",
    foundationNote: "هذه نسخة تطوير للأساس التقني. لا توجد عقارات حقيقية معروضة بعد.",
  },
  status: {
    heading: "حالة النظام",
    api: "واجهة البرمجة",
    database: "قاعدة البيانات",
    postgis: "نظام المعلومات الجغرافية (PostGIS)",
    redis: "Redis (المهام الخلفية)",
    ok: "يعمل",
    degraded: "يعمل جزئياً",
    error: "متوقف",
    unavailable: "غير متاح",
    notConfigured: "عنوان واجهة البرمجة غير مُعدّ",
  },
  errors: {
    NETWORK_ERROR: "تعذّر الاتصال بالخادم. تحقق من اتصالك وحاول مجدداً.",
    NOT_FOUND: "لم يتم العثور على ما تبحث عنه.",
    NOT_AUTHENTICATED: "يرجى تسجيل الدخول للمتابعة.",
    PERMISSION_DENIED: "ليست لديك صلاحية لتنفيذ هذا الإجراء.",
    VALIDATION_ERROR: "بعض البيانات المدخلة غير صحيحة.",
    RATE_LIMITED: "طلبات كثيرة خلال وقت قصير. يرجى الانتظار قليلاً.",
    INTERNAL_ERROR: "حدث خطأ غير متوقع. نعمل على إصلاحه.",
    UNKNOWN: "حدث خطأ. يرجى المحاولة لاحقاً.",
  },
};

export type Dictionary = typeof ar;
export default ar;
